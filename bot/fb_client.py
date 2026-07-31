"""
NB — Client Facebook Graph API.
Envoi de réponses (Messenger, commentaires, réactions).
"""
import hashlib
import hmac

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
    """Répond à un commentaire sur un post."""
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