"""
NB — Génération de réponses IA (Mistral → Gemini).
Personnalité : Geek + Mentor (Nyavodroid). Naturel, imprévisible, humain.
"""
import re
import asyncio
import random
import httpx

from bot.config import MISTRAL_API_KEY, MISTRAL_URL, GEMINI_API_KEY, GEMINI_TEXT_URL, REQUEST_TIMEOUT, BOT_NAME
from bot.language_detector import NOM_LANGUE


def _nettoyer(texte: str) -> str:
    """Nettoie le texte des caractères invisibles et du formatage."""
    texte = re.sub(r'[\u200e\u200f\u200b\u200c\u200d\ufeff\u00ad\u2060\u180e\u202a-\u202e\u2066-\u2069]', '', texte)
    texte = re.sub(r'\*\*(.*?)\*\*', r'\1', texte)
    texte = re.sub(r'\*(.*?)\*', r'\1', texte)
    texte = re.sub(r'^[-•]\s*', '', texte, flags=re.MULTILINE)
    return texte.strip()


def _prompt_reponse(message: str, langue: str, intention: str, contexte_post: str, historique: list[dict]) -> str:
    """
    Construit le prompt SYSTEME avec la personnalité complète.
    C'est ICI que la personnalité du bot est définie.
    """
    nom_langue = NOM_LANGUE.get(langue, "français")

    hist_texte = ""
    if historique:
        hist_texte = "\nDerniers échanges :\n" + "\n".join([f"  - {msg['contenu']}" for msg in historique[-3:]])

    contexte_texte = f"\nContexte du post : « {contexte_post[:150]} »\n" if contexte_post else ""

    # ============================================================
    # ⚠️ PROMPT ORIGINAL - PERSONNALITÉ GEEK + MENTOR ⚠️
    # NE PAS MODIFIER CE BLOC SAUF SI TU VEUX CHANGER LE STYLE
    # ============================================================
    prompt = f"""Tu es {BOT_NAME}, un membre passionné de la communauté Nyavodroid. Tu discutes naturellement, comme sur Discord ou WhatsApp.

RÈGLES ABSOLUES (À NE JAMAIS ENFREINDRE) :
1. NE dis JAMAIS "Salut", "Bonjour" ou "Coucou" si ce n'est pas le tout premier message de la conversation.
2. NE pose PAS de question à la fin de chaque message. Parfois, donne juste l'info et arrête-toi. Parfois, partage une astuce. Parfois, pose une question. VARIE.
3. N'utilise des emojis QUE très rarement (maximum 1 emoji tous les 3 ou 4 messages, et seulement si c'est vraiment pertinent). Pas d'emoji à chaque phrase.
4. NE dis JAMAIS que tu es une IA, un bot ou un assistant. Tu es un humain de la team Nyavodroid.
5. NE fais JAMAIS de listes à puces, de gras, ou de formatage markdown. Écris en texte brut, phrases courtes.

TON STYLE (Geek + Mentor) :
- Tu es direct, chaleureux et tu vas à l'essentiel.
- Tu utilises le tutoiement.
- Tu adaptes ton langage : si l'utilisateur est formel, sois respectueux. S'il est détendu, sois cool. S'il mélange français/malgache, fais de même.
- Longueur : 1 à 3 phrases maximum. C'est tout.

{contexte_texte}{hist_texte}

Message reçu : "{message}"

Réponds de manière naturelle, imprévisible et humaine, en {nom_langue} :"""
    return prompt


async def generer_reponse(
    message: str,
    langue: str,
    intention: str,
    contexte_post: str = "",
    historique: list[dict] | None = None
) -> str:
    """
    Génère une réponse via Mistral ou Gemini.
    Ajoute une pause de réflexion pour simuler l'humain.
    """
    if historique is None:
        historique = []

    prompt = _prompt_reponse(message, langue, intention, contexte_post, historique)

    # === SIMULATION RÉFLEXION HUMAINE (1-3s) ===
    await asyncio.sleep(random.uniform(1.0, 3.0))

    # Tentative Mistral
    if MISTRAL_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(
                    MISTRAL_URL,
                    headers={
                        "Authorization": f"Bearer {MISTRAL_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "mistral-small-latest",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 150,
                        "temperature": 0.9  # Légèrement plus créatif
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["choices"][0]["message"]["content"])
                print(f"🧠 Mistral: {reponse[:50]}...")
                return reponse
        except Exception as e:
            print(f"⚠️  Mistral échoué : {e}")

    # Fallback Gemini
    if GEMINI_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(
                    f"{GEMINI_TEXT_URL}?key={GEMINI_API_KEY}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "maxOutputTokens": 150,
                            "temperature": 0.9
                        }
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
                print(f"🧠 Gemini: {reponse[:50]}...")
                return reponse
        except Exception as e:
            print(f"⚠️  Gemini échoué : {e}")

    # Fallback ultime
    return "Merci pour ton message, je regarde ça et je reviens vers toi !"