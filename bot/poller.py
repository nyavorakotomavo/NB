#!/usr/bin/env python3
"""
NB — Polling des commentaires (Option A : Railway, 30 s, tâche de fond).

Contourne le blocage du webhook en mode Dev : au lieu d'attendre que Facebook
pousse les événements, c'est NB qui va LIRE le feed de la Page (action admin
standard, autorisée pour TOUS les commentateurs, sans review ni testeur).

Cycle toutes les 30 s :
  1. GET /{page}/posts?fields=comments{...}&since=<7j>   (fenêtre glissante)
  2. Filtre : on ignore les commentaires venant de la Page (anti-boucle-infinie)
  3. Filtre : on ne traite que created_time > last_ts  +  dédup par id (mémoire)
  4. Réponse IA (Mistral FR/EN → Gemini MG/fallback), même langue que le commentaire
  5. POST /{comment_id}/comments  +  marquage "vu"

Sécurité intégrée :
  - asyncio.Lock  → un seul cycle à la fois (pas de chevauchement à 30 s)
  - since = MAINTENANT au 1er lancement → on ne répond JAMAIS au passé (anti-spam)
  - compteur d'échecs par id → 3 ratés = on abandonne ce commentaire (anti-spam logs)
  - TOUT est try/excepté → le poller ne peut JAMAIS tuer uvicorn
  - aucune dépendance Supabase → rien à créer côté base
"""

import asyncio
import random
import re
import time
from datetime import datetime, timezone

import requests

from bot import config as C

# ──────────────────────────────────────────────
# Réglages
# ──────────────────────────────────────────────
INTERVAL = 30                 # secondes entre 2 cycles
WINDOW_SECONDS = 7 * 86400    # on regarde les posts des 7 derniers jours
MAX_FAIL_PER_COMMENT = 3      # au-delà, on abandonne ce commentaire
GRAPH = getattr(C, "GRAPH_VERSION", "v25.0")
TIMEOUT = 30

# Modèles Gemini essayés dans l'ordre (pour le malgasy + fallback)
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models/"
GEMINI_MODELS = ["gemini-flash-latest", "gemini-pro-latest", "gemini-2.5-pro"]

# Mots malgaches → route le commentaire vers Gemini (Mistral est faible en MG)
_MG_WORDS = (
    "manao ahoana", "misaotra", "tsara", "veloma", "salama", "mahay",
    "angaha", "azafady", "izaho", "ianao", "izahay", "tena", "mba",
    "malagasy", "ahoana", "inona", "manakory",
)

# ──────────────────────────────────────────────
# État (mémoire, réinitialisé à chaque (re)démarrage)
# ──────────────────────────────────────────────
_lock = asyncio.Lock()
_seen: set[str] = set()                 # comment_id déjà traités cette session
_fail: dict[str, int] = {}              # comment_id -> nb échecs IA
_last_ts: float = time.time()           # depuis quand on a regardé (epoch)
_booted: bool = False


def _log(msg: str) -> None:
    print(f"🔄 [poller] {msg}", flush=True)


# ──────────────────────────────────────────────
# Utilitaires
# ──────────────────────────────────────────────
def _is_malagasy(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in _MG_WORDS)


def _parse_ts(iso: str) -> float:
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S%z").timestamp()
    except Exception:
        return 0.0


def _clean_reply(t: str) -> str:
    t = re.sub(r'[\u200e\u200f\u200b\ufeff]', '', t or '')
    t = t.replace('**', '').replace('*', '').replace('```', '')
    return t.strip()


# ──────────────────────────────────────────────
# Génération de la réponse IA
# ──────────────────────────────────────────────
def _prompt_nb(comment: str, mg: bool) -> str:
    langue = "en malgasy (malagasy)" if mg else "dans la MÊME langue que le commentaire"
    return (
        f"Tu es NB, l'assistant de la page Facebook « Nyavo Channel / Nyavodroid », "
        f"une chaîne tech qui vulgarise l'IA, le code, la cybersécurité et la science "
        f"avec passion et précision.\n\n"
        f"Un abonné a laissé ce commentaire sous un post :\n« {comment} »\n\n"
        f"MISSION : réponds-lui {langue}.\n"
        f"RÈGLES :\n"
        f"- 1 à 3 phrases maximum, concis et chaleureux\n"
        f"- Ton : expert mais accessible, enthousiaste, jamais condescendant\n"
        f"- Si c'est une question : donne une vraie réponse utile\n"
        f"- Si c'est un remerciement ou un compliment : réponds avec chaleur et humilité\n"
        f"- Si c'est un avis : rebondis intelligemment\n"
        f"- PAS de markdown, PAS d'astérisques, PAS de hashtags, PAS de 'en tant qu'IA'\n"
        f"- Juste le texte de la réponse, rien d'autre"
    )


def _mistral(prompt: str) -> str:
    key = getattr(C, "MISTRAL_API_KEY", "")
    if not key:
        raise RuntimeError("MISTRAL_API_KEY absente")
    r = requests.post(
        C.MISTRAL_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "mistral-small-latest",
              "messages": [{"role": "user", "content": prompt}],
              "max_tokens": 300, "temperature": 0.8},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return _clean_reply(r.json()["choices"][0]["message"]["content"])


def _gemini(prompt: str) -> str:
    last = None
    for m in GEMINI_MODELS:
        try:
            r = requests.post(
                f"{GEMINI_BASE}{m}:generateContent?key={C.GEMINI_API_KEY}",
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": 300, "temperature": 0.8}},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            cands = r.json().get("candidates") or []
            parts = (cands[0].get("content", {}) or {}).get("parts") or [] if cands else []
            if not parts:
                raise ValueError("réponse vide")
            txt = _clean_reply(parts[0].get("text", ""))
            if txt:
                return txt
        except Exception as e:
            last = e
            continue
    raise RuntimeError(f"Gemini KO : {last}")


def _gen_reply(comment: str) -> str | None:
    prompt = _prompt_nb(comment, _is_malagasy(comment))
    # 1) Mistral pour FR/EN (et MG en dernier recours)
    if not _is_malagasy(comment):
        try:
            return _mistral(prompt)
        except Exception as e:
            _log(f"Mistral échec → fallback Gemini ({e})")
    # 2) Gemini (MG, ou fallback)
    try:
        return _gemini(prompt)
    except Exception as e:
        _log(f"Gemini échec ({e})")
    # 3) ultime recours : Mistral même pour MG
    if _is_malagasy(comment):
        try:
            return _mistral(prompt)
        except Exception as e:
            _log(f"Mistral fallback échec ({e})")
    return None


# ──────────────────────────────────────────────
# Facebook Graph — lecture + écriture
# ──────────────────────────────────────────────
def _fetch_comments(since_posts: int) -> list[dict]:
    """Renvoie la liste des commentaires récents (top-level) sur les posts de la fenêtre."""
    fields = f"created_time,comments.limit(30){{id,from,message,created_time}}"
    url = f"https://graph.facebook.com/{GRAPH}/{C.FB_PAGE_ID}/posts"
    r = requests.get(
        url,
        params={"fields": fields, "limit": 50, "since": since_posts,
                "access_token": C.FB_PAGE_ACCESS_TOKEN},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    out = []
    for post in r.json().get("data", []):
        for c in (post.get("comments") or {}).get("data", []):
            cid = c.get("id")
            frm = c.get("from") or {}
            msg = (c.get("message") or "").strip()
            cts = _parse_ts(c.get("created_time", ""))
            if cid and msg:
                out.append({"id": cid, "from_id": frm.get("id"), "message": msg, "ts": cts})
    return out


def _send_reply(comment_id: str, text: str) -> bool:
    url = f"https://graph.facebook.com/{GRAPH}/{comment_id}/comments"
    r = requests.post(
        url,
        data={"message": text, "access_token": C.FB_PAGE_ACCESS_TOKEN},
        timeout=TIMEOUT,
    )
    if r.status_code != 200 or "id" not in r.json():
        raise RuntimeError(f"HTTP {r.status_code} : {r.text[:200]}")
    return True


# ──────────────────────────────────────────────
# Le cycle
# ──────────────────────────────────────────────
async def _cycle() -> None:
    global _last_ts, _booted
    cycle_start = time.time()
    since_posts = int(cycle_start - WINDOW_SECONDS)

    try:
        comments = await asyncio.to_thread(_fetch_comments, since_posts)
    except Exception as e:
        _log(f"lecture feed échec : {e}")
        return

    # Au tout 1er cycle : on cale le curseur à MAINTENANT (on ne répond pas au passé)
    if not _booted:
        _booted = True
        _last_ts = cycle_start
        _log(f"démarrage — {len(comments)} commentaire(s) en mémoire, curseur = maintenant (aucun spam du passé)")
        return

    nouveaux = [c for c in comments
                if c["ts"] > _last_ts
                and c["id"] not in _seen
                and c["from_id"] != C.FB_PAGE_ID      # ← anti-boucle-infinie
                and c["from_id"]]                       # on ignore les "from" absents

    if nouveaux:
        _log(f"{len(nouveaux)} nouveau(x) commentaire(s) à traiter")

    for c in nouveaux:
        cid, msg = c["id"], c["message"]
        try:
            reply = await asyncio.to_thread(_gen_reply, msg)
            if not reply:
                raise RuntimeError("réponse vide")
            await asyncio.to_thread(_send_reply, cid, reply)
            _seen.add(cid)
            _fail.pop(cid, None)
            _log(f"✅ répondu à {cid[:12]}… → {reply[:60]}")
        except Exception as e:
            n = _fail.get(cid, 0) + 1
            _fail[cid] = n
            _log(f"⚠️ échec sur {cid[:12]}… ({n}/{MAX_FAIL_PER_COMMENT}) : {e}")
            if n >= MAX_FAIL_PER_COMMENT:
                _seen.add(cid)                      # on abandonne ce commentaire
                _log(f" {cid[:12]}… abandonné après {n} échecs")

    _last_ts = cycle_start                          # curseur = début de ce cycle


# ──────────────────────────────────────────────
# Boucle principale (ne lève JAMAIS)
# ──────────────────────────────────────────────
async def start_polling() -> None:
    _log(f"background task démarrée — intervalle {INTERVAL}s, page {C.FB_PAGE_ID}")
    while True:
        try:
            async with _lock:                       # 1 cycle à la fois
                await _cycle()
        except asyncio.CancelledError:
            _log("task annulée — arrêt")
            raise
        except Exception as e:
            _log(f"cycle crashé (ignoré, on continue) : {e}")
        try:
            await asyncio.sleep(INTERVAL)
        except asyncio.CancelledError:
            raise