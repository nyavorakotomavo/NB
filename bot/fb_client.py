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
    """Vérifie la signature du webhook Facebook."""
    expected = "sha256=" + hmac.new(
        FB_APP_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
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
            if resp.status_code == 200:
                print(f"✏️  Typing activé pour {sender_id}")
            else:
                print(f"⚠️  Typing échoué : {resp.status_code}")
    except Exception as e:
        print(f"⚠️  Erreur action frappe : {e}")


async def _desactiver_action_frappe(sender_id: str) -> None:
    """Désactive l'indicateur 'est en train d'écrire...'."""
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
    """
    Envoie un message privé Messenger.
    Retourne True si réussi, False sinon.
    """
    if not texte or not texte.strip():
        return False

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            payload = {
                "recipient": {"id": sender_id},
                "message": {"text": texte}
            }
            resp = await client.post(
                f"{BASE}/me/messages",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                json=payload
            )

            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ Message envoyé (ID: {data.get('message_id', '?')})")
                return True
            else:
                print(f"❌ Erreur Facebook {resp.status_code}: {resp.text[:200]}")
                return False
    except Exception as e:
        print(f"❌ Erreur envoi message: {e}")
        return False


async def repondre_commentaire(comment_id: str, texte: str) -> bool:
    """Répond à un commentaire."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BASE}/{comment_id}/comments",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                json={"message": texte}
            )
            if resp.status_code == 200:
                print(f"✅ Commentaire envoyé sur {comment_id}")
                return True
            else:
                print(f"❌ Erreur commentaire: {resp.text[:200]}")
                return False
    except Exception as e:
        print(f"❌ Erreur envoi commentaire: {e}")
        return False


async def commenter_post(post_id: str, texte: str) -> None:
    """Poste un commentaire sur un post."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BASE}/{post_id}/comments",
                params={"access_token": FB_PAGE_ACCESS_TOKEN},
                json={"message": texte}
            )
            if resp.status_code != 200:
                print(f"⚠️  Commentaire post échoué: {resp.text[:100]}")
    except Exception as e:
        print(f"⚠️  Erreur commentaire post: {e}")


async def get_post_message(post_id: str) -> str:
    """Récupère le message d'un post."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE}/{post_id}",
                params={"access_token": FB_PAGE_ACCESS_TOKEN, "fields": "message"}
            )
            resp.raise_for_status()
            return resp.json().get("message", "")[:300]
    except Exception as e:
        print(f"⚠️  Erreur récupération post: {e}")
        return ""


async def get_derniers_posts() -> list[dict]:
    """Récupère les derniers posts de la page."""
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
    except Exception as e:
        print(f"⚠️  Erreur récupération posts: {e}")
        return []


# ──────────────────────────────────────────────
# LOGIQUE HUMAINE : Délais + Typing + Découpage
# ──────────────────────────────────────────────
async def envoyer_message_humain(sender_id: str, texte: str, type_envoi: str = "message") -> None:
    """
    Simule un humain :
    1. Délai de "lecture" (2 à 6 secondes)
    2. Indicateur de frappe ("...") pour Messenger
    3. Envoi en plusieurs bulles avec délais naturels (2-5s)
    4. Désactive le typing après l'envoi
    """
    if not texte or not texte.strip():
        print("⚠️  Texte vide, rien à envoyer.")
        return

    # 1. Délai de lecture (l'humain lit avant de répondre)
    await asyncio.sleep(random.uniform(2.0, 5.0))

    # 2. Typing pour Messenger
    if type_envoi == "message":
        await _envoyer_action_frappe(sender_id)
        # L'humain "tape" pendant 2-4 secondes
        await asyncio.sleep(random.uniform(2.0, 4.0))

    # 3. Envoi
    if type_envoi == "commentaire":
        # Pour les commentaires: tout en une fois
        await repondre_commentaire(sender_id, texte)
    else:
        # Pour Messenger: découpage limité à 3 phrases MAX
        phrases = re.split(r'(?<=[.!?]) +', texte.strip())
        phrases = [p for p in phrases if p.strip()]

        # Limiter à 3 phrases pour éviter la rafale
        if len(phrases) > 3:
            phrases = phrases[:3]
            # Ajouter "..." pour montrer qu'il y a la suite
            phrases[-1] = phrases[-1] + "..."

        if len(phrases) <= 1:
            await repondre_message(sender_id, texte)
        else:
            for i, phrase in enumerate(phrases):
                if not phrase.strip():
                    continue

                # Envoi de la phrase
                success = await repondre_message(sender_id, phrase.strip())

                # Délai entre les bulles (2-5s) SAUF si erreur
                if success and i < len(phrases) - 1:
                    attente = random.uniform(2.0, 5.0)
                    # Pause plus longue tous les 2 messages
                    if (i + 1) % 2 == 0:
                        attente += random.uniform(1.0, 3.0)
                    await asyncio.sleep(attente)

    # 4. Désactiver le typing
    if type_envoi == "message":
        await _desactiver_action_frappe(sender_id)