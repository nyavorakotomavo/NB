"""
NB — Client Facebook Graph API.
CORRECTIONS :
- get_derniers_posts_page() pour lire les vrais posts (source de vérité)
- Délai de frappe réaliste (15s base + temps de lecture)
- Anti-doublon basé sur l'ID du message (géré dans server.py, mais sécurité ici aussi)
"""
import asyncio
import hashlib
import hmac
import random
import time
import httpx
from bot.config import FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN, FB_APP_SECRET, GRAPH_VERSION

BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Cache local de sécurité (au cas où server.py rate un doublon)
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

async def get_derniers_posts_page() -> list[dict]:
    """
    🆕 LIT LES VRAIS POSTS publiés sur la page.
    C'est la source de vérité pour éviter que le bot n'invente du contenu.
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE}/{FB_PAGE_ID}/posts",
                params={
                    "access_token": FB_PAGE_ACCESS_TOKEN,
                    "fields": "message,created_time",
                    "limit": 5  # On prend les 5 derniers
                }
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
    except Exception as e:
        print(f"⚠️ Erreur lecture posts FB : {e}")
        return []

def _calculer_delai_humain(longueur_texte: int) -> float:
    """
    Calcule un délai réaliste :
    - 15s minimum (temps de lecture + réflexion)
    - 50ms par caractère (vitesse de frappe)
    - Variance aléatoire (2-8s)
    """
    base = 15.0
    frappe = longueur_texte * 0.05
    variance = random.uniform(2.0, 8.0)
    total = base + frappe + variance
    return min(total, 45.0)  # Plafond à 45s

async def envoyer_message_humain(sender_id: str, texte: str, type_envoi: str = "message") -> None:
    """
    Simule un humain réel :
    - Vérifie le cache (sécurité doublon)
    - Attend 15s+ (délai réaliste)
    - Affiche "en train d'écrire..."
    - Envoie UN SEUL message
    """
    if not texte or not texte.strip():
        return

    # Sécurité doublon locale
    clef_cache = f"{sender_id}_{texte[:30]}"
    now = time.time()
    if clef_cache in _derniers_envois:
        if now - _derniers_envois[clef_cache] < 60:
            print(f"⏭️ Message déjà envoyé récemment, ignoré (sécurité fb_client).")
            return
    _derniers_envois[clef_cache] = now

    # Délai humain réaliste
    delai = _calculer_delai_humain(len(texte))
    print(f"⏳ Délai humain : {delai:.1f}s pour {len(texte)} chars")
    await asyncio.sleep(delai)

    # Typing indicator
    if type_envoi == "message":
        await _envoyer_action_frappe(sender_id)
        await asyncio.sleep(random.uniform(1.0, 2.5))

    # Envoi UNIQUE
    if type_envoi == "commentaire":
        await repondre_commentaire(sender_id, texte)
    else:
        await repondre_message(sender_id, texte)

    # Stop typing
    if type_envoi == "message":
        await _desactiver_action_frappe(sender_id)