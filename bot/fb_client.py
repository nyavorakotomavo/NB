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

def verifier_signature(payload: bytes, signature: str) -> bool:
    expected = "sha256=" + hmac.new(FB_APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

async def _envoyer_action_frappe(sender_id: str) -> None:
    """Active l'indicateur 'est en train d'écrire...' sur Messenger."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{BASE}/me/messages",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                json={"recipient": {"id": sender_id}, "sender_action": "typing_on"}
            )
            print(f"✏️  Action frappe envoyée à {sender_id}: {resp.status_code}")
    except Exception as e:
        print(f"⚠️  Erreur action frappe : {e}")

async def repondre_message(sender_id: str, texte: str) -> None:
    """Envoie un message privé Messenger."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            payload = {
                "recipient": {"id": sender_id},
                "message": {"text": texte}
            }
            print(f"📤 Envoi à {sender_id}: {texte[:30]}...")
            resp = await client.post(
                f"{BASE}/me/messages",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                json=payload
            )
            print(f"📥 Réponse Facebook: {resp.status_code} - {resp.text[:200]}")
            resp.raise_for_status()
            print(f"✅ Message envoyé à {sender_id}")
    except Exception as e:
        print(f"❌ Erreur envoi message : {e}")

async def repondre_commentaire(comment_id: str, texte: str) -> None:
    """Répond à un commentaire."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BASE}/{comment_id}/comments",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                json={"message": texte}
            )
            print(f"📥 Réponse commentaire: {resp.status_code} - {resp.text[:200]}")
            resp.raise_for_status()
            print(f"✅ Commentaire envoyé à {comment_id}")
    except Exception as e:
        print(f"❌ Erreur envoi commentaire : {e}")

async def commenter_post(post_id: str, texte: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            await client.post(f"{BASE}/{post_id}/comments", params={"access_token": FB_PAGE_ACCESS_TOKEN}, json={"message": texte})
    except Exception as e:
        print(f"⚠️  Erreur commentaire post : {e}")

async def get_post_message(post_id: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{BASE}/{post_id}", params={"access_token": FB_PAGE_ACCESS_TOKEN, "fields": "message"})
            resp.raise_for_status()
            return resp.json().get("message", "")[:300]
    except Exception as e:
        print(f"⚠️  Erreur récupération post : {e}")
        return ""

async def get_derniers_posts() -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{BASE}/{FB_PAGE_ID}/posts", params={"access_token": FB_PAGE_ACCESS_TOKEN, "fields": "id,message,created_time", "limit": 10})
            resp.raise_for_status()
            return resp.json().get("data", [])
    except Exception as e:
        print(f"⚠️  Erreur récupération posts : {e}")
        return []


# ──────────────────────────────────────────────
# Logique Humaine : Délai de lecture + Frappe
# ──────────────────────────────────────────────
async def envoyer_message_humain(sender_id: str, texte: str, type_envoi: str = "message") -> None:
    """
    Simule un humain : 
    1. Délai de "lecture" (2 à 6 secondes)
    2. Indicateur de frappe ("...") pour Messenger
    3. Envoi (en un bloc pour commentaire, ou découpé pour Messenger)
    """
    print(f"📨 envoyer_message_humain({sender_id}, type={type_envoi})")

    # 1. Délai de lecture réaliste (l'humain lit la notif avant de taper)
    delai_lecture = random.uniform(2.0, 6.0)
    await asyncio.sleep(delai_lecture)

    # 2. Si c'est Messenger, on active les "..."
    if type_envoi == "message":
        await _envoyer_action_frappe(sender_id)
        # Petit délai pendant qu'il "tape"
        await asyncio.sleep(random.uniform(1.5, 3.0))

    # 3. Envoi
    if type_envoi == "commentaire":
        # Pour les commentaires, on envoie TOUT en une fois
        await repondre_commentaire(sender_id, texte)
    else:
        # Pour Messenger, on peut découper si c'est long
        phrases = re.split(r'(?<=[.!?]) +', texte.strip())
        if len(phrases) <= 1:
            await repondre_message(sender_id, texte)
        else:
            for i, phrase in enumerate(phrases):
                if not phrase.strip():
                    continue
                await repondre_message(sender_id, phrase.strip())
                if i < len(phrases) - 1:
                    attente = random.uniform(1.5, 4.5)
                    if (i + 1) % 3 == 0:
                        attente += random.uniform(3.0, 7.0)
                    await asyncio.sleep(attente)