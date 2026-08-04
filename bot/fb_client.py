"""
NB — Client Facebook Graph API.
CORRECTIONS :
- Délai de frappe calculé selon la longueur du message (50ms/char + variance)
- Minimum 15s entre réception et réponse
- Anti-rafale : UN SEUL message par cycle, jamais de doublons
"""
import asyncio
import hashlib
import hmac
import random
import time
import httpx
from bot.config import FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN, FB_APP_SECRET, GRAPH_VERSION

BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Cache anti-doublons (60 secondes)
_derniers_messages_envoyes: dict[str, float] = {}
_CACHE_DUREE = 60.0

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

def _calculer_delai_frappe(longueur_texte: int) -> float:
    """
    Calcule un délai de frappe réaliste :
    - Base : 15 secondes minimum (temps de lecture + réflexion)
    - Frappe : 50ms par caractère + variance aléatoire
    - Plafond : 45 secondes max
    """
    base = 15.0
    frappe = longueur_texte * 0.05
    variance = random.uniform(2.0, 8.0)
    total = base + frappe + variance
    return min(total, 45.0)

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

async def envoyer_message_humain(sender_id: str, texte: str, type_envoi: str = "message") -> None:
    """
    Simule un humain réel :
    - Vérifie le cache (60s) → pas de doublons
    - Attend 15s minimum + temps de frappe réaliste
    - Affiche "en train d'écrire..."
    - Envoie UN SEUL message
    """
    if not texte or not texte.strip():
        return
    
    # Anti-doublons
    clef_cache = f"{sender_id}_{texte[:30]}"
    if clef_cache in _derniers_messages_envoyes:
        temps_ecoule = time.time() - _derniers_messages_envoyes[clef_cache]
        if temps_ecoule < _CACHE_DUREE:
            print(f"⏭️  Message déjà envoyé il y a {temps_ecoule:.0f}s, ignoré.")
            return
    
    _derniers_messages_envoyes[clef_cache] = time.time()
    
    # Délai humain réaliste
    delai = _calculer_delai_frappe(len(texte))
    print(f"⏳ Délai humain : {delai:.1f}s pour {len(texte)} caractères")
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