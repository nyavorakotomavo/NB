#!/usr/bin/env python3
"""
NB — Polling des commentaires (Option A : Railway, 30 s, tâche de fond).

Contourne le blocage du webhook en mode Dev : NB va LIRE le feed de la Page
(action admin standard, OK pour TOUS les commentateurs, sans review ni testeur).

Le poller NE RÉÉCRIT PAS la logique IA : il réutilise le cerveau du serveur
(ai_responder / language_detector / intent_analyzer / fb_client / conversation_store).

⚠️ MODE DEBUG ACTIF : logs verbeux temporaires pour diagnostiquer pourquoi les
   nouveaux commentaires sont filtrés. À retirer une fois le bug identifié.
"""

import asyncio
import time
from datetime import datetime, timezone

import requests

from bot.config import FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN, GRAPH_VERSION
from bot.fb_client import repondre_commentaire, get_post_message
from bot.ai_responder import generer_reponse
from bot.language_detector import detecter_langue
from bot.intent_analyzer import analyser_intention
from bot.conversation_store import (
    sauvegarder_message,
    get_historique,
    log_interaction,
)

# ──────────────────────────────────────────────
# Réglages
# ──────────────────────────────────────────────
INTERVAL = 30                 # secondes entre 2 cycles
WINDOW_SECONDS = 7 * 86400    # on regarde les posts des 7 derniers jours
MAX_FAIL_PER_COMMENT = 3      # au-delà, on abandonne ce commentaire
TIMEOUT = 30

# ──────────────────────────────────────────────
# État (mémoire ; réinitialisé à chaque (re)démarrage)
# ──────────────────────────────────────────────
_lock = asyncio.Lock()
_seen: set[str] = set()
_fail: dict[str, int] = {}
_last_ts: float = time.time()
_booted: bool = False


def _log(msg: str) -> None:
    print(f"🔄 [poller] {msg}", flush=True)


def _parse_ts(iso: str) -> float:
    """Parse un created_time Facebook, robuste aux variantes de fuseau (Z, +0000, +00:00)."""
    if not iso:
        return 0.0
    s = iso.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # fuseau sans deux-points ex: +0000 -> +00:00
    if len(s) >= 5 and s[-5] in "+-" and s[-3] != ":":
        s = s[:-2] + ":" + s[-2:]
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue
    # ultime recours : fromisoformat (3.11+)
    try:
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0.0


def _fmt(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")
    except Exception:
        return "?"


def _raisons(c: dict) -> list[str]:
    r = []
    if c["ts"] <= _last_ts:
        r.append(f"trop vieux (ts {_fmt(c['ts'])} <= curseur {_fmt(_last_ts)})")
    if c["id"] in _seen:
        r.append("déjà vu")
    if not c["from_id"]:
        r.append("from vide")
    elif c["from_id"] == FB_PAGE_ID:
        r.append("c'est la Page")
    return r or ["? (raison inconnue)"]


# ──────────────────────────────────────────────
# Facebook Graph — lecture brute
# ──────────────────────────────────────────────
def _fetch_recent_comments(since_posts: int) -> list[dict]:
    fields = "created_time,comments.limit(30){id,from,message,created_time}"
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{FB_PAGE_ID}/posts"
    r = requests.get(
        url,
        params={
            "fields": fields,
            "limit": 50,
            "since": since_posts,
            "access_token": FB_PAGE_ACCESS_TOKEN,
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    out = []
    for post in r.json().get("data", []):
        pid = post.get("id", "")
        for cmm in (post.get("comments") or {}).get("data", []):
            cid = cmm.get("id")
            frm = cmm.get("from") or {}
            msg = (cmm.get("message") or "").strip()
            ts = _parse_ts(cmm.get("created_time", ""))
            if cid and msg:
                out.append({
                    "id": cid,
                    "from_id": frm.get("id"),
                    "message": msg,
                    "ts": ts,
                    "post_id": pid,
                })
    return out


# ──────────────────────────────────────────────
# Traitement d'UN commentaire = même séquence que le webhook
# ──────────────────────────────────────────────
async def _traiter_commentaire(c: dict) -> None:
    cid = c["id"]
    sender = c["from_id"] or ""
    texte = c["message"]
    post_id = c.get("post_id", "")
    t0 = time.time()

    langue = detecter_langue(texte)
    intention = analyser_intention(texte)

    if intention == "spam":
        _log(f"🚮 spam ignoré {cid[:12]}…")
        _seen.add(cid)
        return

    contexte = await get_post_message(post_id) if post_id else ""
    historique = get_historique(sender, "comment")

    sauvegarder_message(sender, "comment", "user", texte, langue, post_id)

    reponse = await generer_reponse(
        message=texte,
        langue=langue,
        intention=intention,
        contexte_post=contexte,
        historique=historique,
    )

    await repondre_commentaire(cid, reponse)

    sauvegarder_message(sender, "comment", "bot", reponse, langue, post_id)
    temps = time.time() - t0
    log_interaction(sender, "commentaire", langue, intention, temps, post_id)

    _log(f"✅ [{langue}/{intention}] {cid[:12]}… → {reponse[:60]} ({temps:.1f}s)")


# ──────────────────────────────────────────────
# Le cycle
# ──────────────────────────────────────────────
async def _cycle() -> None:
    global _last_ts, _booted
    cycle_start = time.time()
    since_posts = int(cycle_start - WINDOW_SECONDS)

    try:
        comments = await asyncio.to_thread(_fetch_recent_comments, since_posts)
    except Exception as e:
        _log(f"lecture feed échec : {e}")
        return

    if not _booted:
        _booted = True
        _last_ts = cycle_start
        _log(f"démarrage — {len(comments)} commentaire(s) vus, curseur = maintenant ({_fmt(_last_ts)})")
        return

    # ── DEBUG : ce que l'API nous renvoie ce cycle ──
    ts_max = max((c["ts"] for c in comments), default=0.0)
    _log(f"🔍 DEBUG cycle : {len(comments)} brut(s) | ts_max={_fmt(ts_max)} | curseur={_fmt(_last_ts)}")
    for c in comments[:3]:
        _log(f"     ↳ id={c['id'][:18]}… from={c['from_id']} ts={_fmt(c['ts'])} « {c['message'][:35]} »")

    nouveaux = [
        c for c in comments
        if c["ts"] > _last_ts
        and c["id"] not in _seen
        and c["from_id"]
        and c["from_id"] != FB_PAGE_ID
    ]

    if nouveaux:
        _log(f"{len(nouveaux)} nouveau(x) commentaire(s) à traiter")
    elif comments:
        # ── DEBUG : pourquoi TOUT est filtré ──
        _log(f"🔍 DEBUG filtrage : 0 nouveau sur {len(comments)} brut(s). Raisons (3 premiers) :")
        for c in comments[:3]:
            _log(f"     ✖ {c['id'][:18]}… → {' | '.join(_raisons(c))}")

    for c in nouveaux:
        cid = c["id"]
        try:
            await _traiter_commentaire(c)
            _seen.add(cid)
            _fail.pop(cid, None)
        except Exception as e:
            n = _fail.get(cid, 0) + 1
            _fail[cid] = n
            _log(f"⚠️ échec {cid[:12]}… ({n}/{MAX_FAIL_PER_COMMENT}) : {e}")
            if n >= MAX_FAIL_PER_COMMENT:
                _seen.add(cid)
                _log(f"🚫 {cid[:12]}… abandonné après {n} échecs")

    _last_ts = cycle_start


# ──────────────────────────────────────────────
# Boucle principale (ne lève JAMAIS)
# ──────────────────────────────────────────────
async def start_polling() -> None:
    _log(f"tâche de fond démarrée — intervalle {INTERVAL}s, page {FB_PAGE_ID}")
    while True:
        try:
            async with _lock:
                await _cycle()
        except asyncio.CancelledError:
            _log("tâche annulée — arrêt")
            raise
        except Exception as e:
            _log(f"cycle crashé (ignoré, on continue) : {e}")
        try:
            await asyncio.sleep(INTERVAL)
        except asyncio.CancelledError:
            raise