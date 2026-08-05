"""
NB — Client Facebook Graph API.
CORRECTION : get_derniers_posts_page robuste + délai humain.
"""
import asyncio
import hashlib
import hmac
import random
import time
import httpx
from bot.config import FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN, FB_APP_SECRET, GRAPH_VERSION

BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Cache local de sécurité
_derniers_envois: dict[str, float] = {}

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
            return resp.status_code == 200
    except Exception:
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

async def get_derniers_posts_page() -> list[dict]:
    """
    LIT LES VRAIS POSTS.
    Si échec, renvoie une liste vide (le prompt gérera le fallback).
    """
    if not FB_PAGE_ID or not FB_PAGE_ACCESS_TOKEN:
        print("⚠️ Config FB manquante pour lire les posts")
        return []
        
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # On demande explicitement les posts publiés par la page
            resp = await client.get(
                f"{BASE}/{FB_PAGE_ID}/feed", 
                params={
                    "access_token": FB_PAGE_ACCESS_TOKEN,
                    "fields": "message,created_time",
                    "limit": 5
                }
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            # Filtrer les posts sans texte (ex: juste une photo)
            return [p for p in data if p.get("message")]
    except Exception as e:
        print(f"⚠️ Erreur lecture posts FB : {e}")
        return []

def _calculer_delai_humain(longueur_texte: int) -> float:
    base = 15.0
    frappe = longueur_texte * 0.05
    variance = random.uniform(2.0, 8.0)
    return min(base + frappe + variance, 45.0)

async def envoyer_message_humain(sender_id: str, texte: str, type_envoi: str = "message") -> None:
    if not texte or not texte.strip():
        return

    clef_cache = f"{sender_id}_{texte[:30]}"
    now = time.time()
    if clef_cache in _derniers_envois:
        if now - _derniers_envois[clef_cache] < 60:
            print(f"⏭️ Message déjà envoyé récemment, ignoré.")
            return
    _derniers_envois[clef_cache] = now

    delai = _calculer_delai_humain(len(texte))
    print(f"⏳ Délai humain : {delai:.1f}s")
    await asyncio.sleep(delai)

    if type_envoi == "message":
        await _envoyer_action_frappe(sender_id)
        await asyncio.sleep(random.uniform(1.0, 2.5))

    if type_envoi == "commentaire":
        await repondre_commentaire(sender_id, texte)
    else:
        await repondre_message(sender_id, texte)

    if type_envoi == "message":
        await _desactiver_action_frappe(sender_id)