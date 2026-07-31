#!/usr/bin/env python3
"""
NB — Polling des commentaires (Option A : Railway, 30 s, tâche de fond).

Contourne le blocage du webhook en mode Dev : au lieu d'attendre que Facebook
pousse les événements, NB va LIRE le feed de la Page (action admin standard,
autorisée pour TOUS les commentateurs, sans review ni testeur).

IMPORTANT : ce poller NE RÉÉCRIT PAS la logique IA. Il réutilise le cerveau du
serveur (bot.ai_responder / language_detector / intent_analyzer / fb_client /
conversation_store). Webhook et polling partagent donc le même NB, le même
historique, les mêmes analytics, et le même filtre anti-spam.

Cycle toutes les 30 s :
  1. GET /{page}/posts?fields=comments{...}   (fenêtre 7 j)
  2. Filtre anti-boucle : on ignore from.id == FB_PAGE_ID
  3. Filtre nouveauté  : created_time > last_ts  +  dédup par id (mémoire)
  4. Cerveau du bot    : langue → intention (spam ignoré) → réponse IA → envoi
  5. Marquage "vu"     + analytics Supabase

Sécurité :
  - asyncio.Lock  → 1 seul cycle à la fois (pas de chevauchement à 30 s)
  - since = MAINTENANT au 1er lancement → JAMAIS de spam du passé
  - compteur d'échecs par id → 3 ratés = abandon (pas de spam de logs)
  - TOUT est try/excepté → le poller ne peut JAMAIS tuer uvicorn
  - aucune table Supabase à créer (déjà géré par conversation_store)
"""

import asyncio
import time
from datetime import datetime

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
_seen: set[str] = set()        # comment_id déjà traités cette session
_fail: dict[str, int] = {}     # comment_id -> nb échecs consécutifs
_last_ts: float = time.time()  # horizon "nouveauté" (epoch)
_booted: bool = False


def _log(msg: str) -> None:
    print(f"🔄 [poller] {msg}", flush=True)


def _parse_ts(iso: str) -> float:
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S%z").timestamp()
    except Exception:
        return 0.0


# ──────────────────────────────────────────────
# Facebook Graph — lecture brute (requests synchrone → to_thread)
# ──────────────────────────────────────────────
def _fetch_recent_comments(since_posts: int) -> list[dict]:
    """Commentaires de 1er niveau sur les posts de la fenêtre."""
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

    # Analyse (cerveau du bot)
    langue = detecter_langue(texte)
    intention = analyser_intention(texte)

    # Anti-spam (identique au webhook)
    if intention == "spam":
        _log(f"🚮 spam ignoré {cid[:12]}…")
        _seen.add(cid)
        return

    # Contexte du post + historique (pour une réponse cohérente)
    contexte = await get_post_message(post_id) if post_id else ""
    historique = get_historique(sender, "comment")

    # On mémorise le message entrant
    sauvegarder_message(sender, "comment", "user", texte, langue, post_id)

    # Réponse IA (Mistral FR/EN → Gemini MG/fallback, avec historique)
    reponse = await generer_reponse(
        message=texte,
        langue=langue,
        intention=intention,
        contexte_post=contexte,
        historique=historique,
    )

    # Envoi sous le commentaire (au nom de la Page)
    await repondre_commentaire(cid, reponse)

    # On mémorise la réponse + analytics
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

    # Lecture (synchrone → ne bloque pas la boucle asyncio du serveur)
    try:
        comments = await asyncio.to_thread(_fetch_recent_comments, since_posts)
    except Exception as e:
        _log(f"lecture feed échec : {e}")
        return

    # 1er lancement : on cale le curseur à MAINTENANT (aucun spam du passé)
    if not _booted:
        _booted = True
        _last_ts = cycle_start
        _log(f"démarrage — {len(comments)} commentaire(s) vus, curseur = maintenant")
        return

    # Nouveautés : récents + pas encore vus + pas nous-mêmes
    nouveaux = [
        c for c in comments
        if c["ts"] > _last_ts
        and c["id"] not in _seen
        and c["from_id"]
        and c["from_id"] != FB_PAGE_ID     # ← anti-boucle-infinie
    ]
    if nouveaux:
        _log(f"{len(nouveaux)} nouveau(x) commentaire(s) à traiter")

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
                _seen.add(cid)               # on abandonne ce commentaire
                _log(f"🚫 {cid[:12]}… abandonné après {n} échecs")

    _last_ts = cycle_start                   # curseur = début de ce cycle


# ──────────────────────────────────────────────
# Boucle principale (ne lève JAMAIS)
# ──────────────────────────────────────────────
async def start_polling() -> None:
    _log(f"tâche de fond démarrée — intervalle {INTERVAL}s, page {FB_PAGE_ID}")
    while True:
        try:
            async with _lock:                # 1 cycle à la fois
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