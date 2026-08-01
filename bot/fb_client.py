"""
NB — Client Facebook Graph API.
Envoi de réponses avec délai humain (Message Splitting pour Messenger uniquement).
"""
import asyncio
import hashlib
import hmac
import random
import re

import httpx

from bot.config import (
    FB_PAGE_ID,
    FB_PAGE_ACCESS_TOKEN,
    FB_APP_SECRET,
    GRAPH_VERSION,
)

BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


def verifier_signature(payload: bytes, signature: str) -> bool:
    """Vérifie que le webhook vient bien de Facebook (X-Hub-Signature-256)."""
    expected = "sha256=" + hmac.new(
        FB_APP_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def repondre_message(sender_id: str, texte: str) -> None:
    """Envoie un message Messenger à un utilisateur."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE}/me/messages",
            params={"access_token": FB_PAGE_ACCESS_TOKEN},
            json={
                "recipient": {"id": sender_id},
                "message": {"text": texte},
            },
        )
        resp.raise_for_status()


async def repondre_commentaire(comment_id: str, texte: str) -> None:
    """Répond à un commentaire sur un post (EN UN SEUL BLOC)."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE}/{comment_id}/comments",
            params={"access_token": FB_PAGE_ACCESS_TOKEN},
            json={"message": texte},
        )
        resp.raise_for_status()


async def commenter_post(post_id: str, texte: str) -> None:
    """Poste un commentaire sur un post (ex: remerciement général)."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE}/{post_id}/comments",
            params={"access_token": FB_PAGE_ACCESS_TOKEN},
            json={"message": texte},
        )
        resp.raise_for_status()


async def get_post_message(post_id: str) -> str:
    """Récupère le texte d'un post (pour le contexte)."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE}/{post_id}",
                params={
                    "access_token": FB_PAGE_ACCESS_TOKEN,
                    "fields": "message",
                },
            )
            resp.raise_for_status()
            return resp.json().get("message", "")[:300]
    except Exception:
        return ""


async def get_derniers_posts() -> list[dict]:
    """Récupère les 10 derniers posts de la Page."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE}/{FB_PAGE_ID}/posts",
                params={
                    "access_token": FB_PAGE_ACCESS_TOKEN,
                    "fields": "id,message,created_time",
                    "limit": 10,
                },
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
    except Exception:
        return []


# ──────────────────────────────────────────────
# Message Splitting + Délai de frappe humain
# ──────────────────────────────────────────────
async def envoyer_message_humain(sender_id: str, texte: str, type_envoi: str = "message") -> None:
    """
    Découpe le texte en phrases et les envoie avec un délai naturel.
    ATTENTION : Ne s'applique QU'AU MESSENGER. 
    Pour les commentaires, on envoie tout en une fois pour éviter les réponses imbriquées Facebook.
    """
    # 1. Si c'est un commentaire, on envoie TOUT d'un coup (sécurité Facebook)
    if type_envoi == "commentaire":
        await repondre_commentaire(sender_id, texte)
        return

    # 2. Si c'est un message Messenger, on fait le découpage humain
    phrases = re.split(r'(?<=[.!?]) +', texte.strip())
    
    # Si une seule phrase ou texte trop court, envoi direct
    if len(phrases) <= 1:
        await repondre_message(sender_id, texte)
        return

    # Envoyer les phrases une par une avec délai
    for i, phrase in enumerate(phrases):
        if not phrase.strip():
            continue
        
        # Délai aléatoire entre 1 et 2.5 secondes (simule la frappe)
        delai = random.uniform(1.0, 2.5)
        
        # Pas de délai avant le premier message
        if i > 0:
            await asyncio.sleep(delai)
        
        # Envoyer la phrase
        await repondre_message(sender_id, phrase.strip())