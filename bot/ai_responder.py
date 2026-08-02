"""
NB — Génération de réponses IA (Mistral → Gemini).
Personnalité : Humain, Geek, Mentor.
Règles strictes : pas de questions, pas de salutations, reste dans le sujet.
"""
import re
import asyncio
import random
import httpx

from bot.config import (
    MISTRAL_API_KEY, MISTRAL_URL, GEMINI_API_KEY, GEMINI_TEXT_URL,
    REQUEST_TIMEOUT, BOT_NAME, get_current_date, MAX_HISTORY_TURNS
)
from bot.language_detector import NOM_LANGUE


def _nettoyer(texte: str) -> str:
    """Nettoie le texte des caractères invisibles et du formatage."""
    texte = re.sub(r'[\u200e\u200f\u200b\u200c\u200d\ufeff\u00ad\u2060\u180e\u202a-\u202e\u2066-\u2069]', '', texte)
    texte = re.sub(r'\*\*(.*?)\*\*', r'\1', texte)
    texte = re.sub(r'\*(.*?)\*', r'\1', texte)
    texte = re.sub(r'^[-•]\s*', '', texte, flags=re.MULTILINE)
    return texte.strip()


def _construire_historique(historique: list[dict]) -> str:
    """
    Construit un résumé de l'historique pour le prompt.
    Inclut les 10 derniers échanges pour garder le contexte.
    """
    if not historique:
        return ""

    hist_texte = "\n📜 HISTORIQUE DE LA CONVERSATION :\n"
    for msg in historique[-MAX_HISTORY_TURNS * 2:]:  # Jusqu'à 20 messages
        role = "Utilisateur" if msg.get('role') == 'user' else BOT_NAME
        contenu = msg.get('contenu', '')
        hist_texte += f"- {role} : {contenu}\n"
    return hist_texte


def _prompt_reponse(
    message: str,
    langue: str,
    intention: str,
    contexte_post: str,
    historique: list[dict]
) -> str:
    """
    Construit le prompt avec personnalité HUMAINE + date actuelle + historique complet.
    """
    nom_langue = NOM_LANGUE.get(langue, "français")
    date_actuelle = get_current_date()

    # Construction de l'historique
    hist_texte = _construire_historique(historique)

    contexte_texte = f"\n📌 CONTEXTE DU POST : « {contexte_post[:150]} »\n" if contexte_post else ""

    # ============================================================
    # PROMPT ULTRA-HUMAIN - INTERDICTION TOTALE DE POSER DES QUESTIONS
    # ============================================================
    prompt = f"""Tu es {BOT_NAME}, un humain normal qui discute sur Messenger. Tu es un pote, PAS un assistant.

📅 DATE ACTUELLE : {date_actuelle}

🚨 RÈGLES ABSOLUES (À NE JAMAIS ENFREINDRE) :

1. ❌ **INTERDICTION TOTALE de poser une question.**
   - JAMAIS de "Tu veux... ?", "Est-ce que... ?", "Pourquoi... ?", "Comment... ?"
   - Si tu dois demander quelque chose, transforme-le en affirmation.

2. ❌ **INTERDICTION TOTALE de dire "Salut", "Bonjour", "Yo", "Hey"** sauf si c'est le TOUT PREMIER message.

3. ✅ **RESTE DANS LE SUJET** :
   - Regarde l'historique pour savoir de quoi l'utilisateur a déjà parlé.
   - Si l'utilisateur parle de la date → réponds sur la date.
   - Si l'utilisateur parle de tech → réponds sur la tech.
   - Si l'utilisateur parle d'autre chose → réponds sur ce sujet.
   - Ne force JAMAIS le sujet tech.

4. ✅ **SOIS NATUREL ET IMPRÉVISIBLE** :
   - Parfois donne une info.
   - Parfois partage une anecdote.
   - Parfois donne un avis.
   - Parfois rigole.
   - Mais SURTOUT, ne sois pas mécanique.

5. ❌ **INTERDICTION TOTALE de faire des listes, du markdown, du gras, des puces.**

6. ✅ **Emojis : maximum 1 emoji tous les 3 messages.**

7. ✅ **Longueur : 1 à 3 phrases maximum.**

{contexte_texte}
{hist_texte}

📩 DERNIER MESSAGE DE L'UTILISATEUR : "{message}"

🔑 Consigne finale : Réponds en {nom_langue} comme un humain normal. Pas de questions. Sois naturel. Reste dans le sujet. 1 à 3 phrases.
RÉPONSE :"""
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
    """
    if historique is None:
        historique = []

    prompt = _prompt_reponse(message, langue, intention, contexte_post, historique)

    # Pause réflexion humaine
    await asyncio.sleep(random.uniform(1.0, 2.5))

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
                        "messages": [
                            {"role": "system", "content": "Tu es un humain normal. Tu réponds de manière naturelle, sans poser de questions. Tu utilises le tutoiement."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 120,
                        "temperature": 0.95
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
                            "maxOutputTokens": 120,
                            "temperature": 0.95
                        }
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
                print(f"🧠 Gemini: {reponse[:50]}...")
                return reponse
        except Exception as e:
            print(f"⚠️  Gemini échoué : {e}")

    # Fallback humain
    fallbacks = [
        "Ah ouais, je vois ce que tu veux dire.",
        "Je comprends, c'est pas toujours évident.",
        "Ouais, je suis d'accord avec toi.",
        "C'est marrant que tu dises ça, j'y pensais justement."
    ]
    return random.choice(fallbacks)