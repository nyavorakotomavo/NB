"""
NB — Client Facebook Graph API.
Gestion du délai humain, de l'indicateur de frappe ("...") et de l'envoi.
"""
import asyncio
import hashlib
import hmac
import random
import re
import httpx

from bot.config import FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN, FB_APP_SECRET, GRAPH_VERSION

BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Cache pour éviter les doublons de réponses
_derniers_messages_envoyes: dict[str, str] = {}


def verifier_signature(payload: bytes, signature: str) -> bool:
    expected = "sha256=" + hmac.new(
        FB_APP_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _envoyer_action_frappe(sender_id: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{BASE}/me/messages",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                json={"recipient": {"id": sender_id}, "sender_action": "typing_on"}
            )
    except Exception:
        pass


async def _desactiver_action_frappe(sender_id: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{BASE}/me/messages",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                json={"recipient": {"id": sender_id}, "sender_action": "typing_off"}
            )
    except Exception:
        pass


async def repondre_message(sender_id: str, texte: str) -> bool:
    if not texte or not texte.strip():
        return False

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BASE}/me/messages",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                json={"recipient": {"id": sender_id}, "message": {"text": texte}}
            )
            if resp.status_code == 200:
                print(f"✅ Message envoyé à {sender_id}")
                return True
            else:
                print(f"❌ Erreur {resp.status_code}: {resp.text[:100]}")
                return False
    except Exception as e:
        print(f"❌ Erreur envoi: {e}")
        return False


async def repondre_commentaire(comment_id: str, texte: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BASE}/{comment_id}/comments",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                json={"message": texte}
            )
            return resp.status_code == 200
    except Exception:
        return False


async def commenter_post(post_id: str, texte: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(
                f"{BASE}/{post_id}/comments",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                json={"message": texte}
            )
    except Exception:
        pass


async def get_post_message(post_id: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE}/{post_id}",
                params={"access_token": FB_PAGE_ACCESS_TOKEN, "fields": "message"}
            )
            resp.raise_for_status()
            return resp.json().get("message", "")[:300]
    except Exception:
        return ""


async def get_derniers_posts() -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE}/{FB_PAGE_ID}/posts",
                params={
                    "access_token": FB_PAGE_ACCESS_TOKEN,
                    "fields": "id,message,created_time",
                    "limit": 10
                }
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
    except Exception:
        return []


# ──────────────────────────────────────────────
# ENVOI HUMAIN : UN SEUL MESSAGE PAR RÉPONSE
# ──────────────────────────────────────────────
async def envoyer_message_humain(sender_id: str, texte: str, type_envoi: str = "message") -> None:
    """
    Simule un humain :
    - Délai de lecture (2-4s)
    - Typing
    - Envoi d'UN SEUL message (pas de rafale)
    """
    if not texte or not texte.strip():
        return

    # Vérifier si on a déjà envoyé la même réponse récemment
    clef_cache = f"{sender_id}_{texte[:30]}"
    if clef_cache in _derniers_messages_envoyes:
        print("⏭️  Message déjà envoyé récemment, ignoré.")
        return
    _derniers_messages_envoyes[clef_cache] = texte

    # Délai de lecture
    await asyncio.sleep(random.uniform(2.0, 4.0))

    # Typing
    if type_envoi == "message":
        await _envoyer_action_frappe(sender_id)
        await asyncio.sleep(random.uniform(1.5, 3.0))

    # Envoi d'UN SEUL message (pas de découpage)
    if type_envoi == "commentaire":
        await repondre_commentaire(sender_id, texte)
    else:
        await repondre_message(sender_id, texte)

    # Désactiver le typing
    if type_envoi == "message":
        await _desactiver_action_frappe(sender_id)