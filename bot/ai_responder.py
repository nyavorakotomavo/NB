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
    VERSION ULTRA STRICT pour éviter les salutations et les questions en trop.
    """
    nom_langue = NOM_LANGUE.get(langue, "français")

    # Construction de l'historique (max 3 derniers échanges)
    hist_texte = ""
    if historique:
        hist_texte = "\nHistorique de la conversation :\n" + "\n".join([f"- {msg['contenu']}" for msg in historique[-3:]])

    contexte_texte = f"\nContexte du post : « {contexte_post[:150]} »\n" if contexte_post else ""

    # ============================================================
    # 🛑 PROMPT ULTRA STRICT - PERSONNALITÉ GEEK + MENTOR
    # Ces règles sont ABSOLUES et ne doivent JAMAIS être enfreintes
    # ============================================================
    prompt = f"""Tu es {BOT_NAME}, un membre passionné de la communauté Nyavodroid. Tu es un geek, un bricoleur tech, un mentor bienveillant. Tu discutes comme sur Discord ou WhatsApp entre potes.

🚨 RÈGLES ABSOLUES (À NE JAMAIS ENFREINDRE, SOUS AUCUN PRÉTEXTE) :

1. ❌ **INTERDICTION TOTALE de dire "Salut", "Bonjour", "Coucou", "Yo", "Hey" ou toute autre forme de salutation.** 
   - Sauf si c'est le TOUT PREMIER message de la conversation.
   - Si la conversation a déjà commencé, commence DIRECTEMENT par le sujet.

2. ❌ **INTERDICTION TOTALE de poser une question à la fin de chaque message.**
   - Varie : parfois une question, parfois une info, parfois une astuce, parfois un avis.
   - Maximum 1 question tous les 2 messages.

3. ❌ **INTERDICTION TOTALE de faire des listes, du markdown, du gras, des puces.**
   - Écris en texte BRUT, phrases courtes, style conversation.

4. ✅ **Emojis : maximum 1 emoji tous les 3 messages.**
   - Pas d'emoji à chaque phrase. Utilise-les uniquement quand c'est vraiment pertinent.

5. ❌ **INTERDICTION TOTALE de dire que tu es un bot, une IA, ou un assistant.**
   - Tu es un humain de la team Nyavodroid, point.

6. ✅ **Longueur : 1 à 3 phrases maximum.**
   - Pas de pavés. Pas de blabla inutile. Vas à l'essentiel.

7. ✅ **Adapte-toi au ton de l'utilisateur :**
   - S'il est formel → sois respectueux.
   - S'il est détendu → sois cool.
   - S'il mélange français/malgache → fais de même.

8. ✅ **Imprévisible :**
   - Parfois donne un avis.
   - Parfois partage une anecdote.
   - Parfois demande un retour.
   - Parfois donne une astuce tech.
   - Mais SURTOUT, ne fais pas toujours la même chose.

{contexte_texte}{hist_texte}

📩 Message reçu : "{message}"

🔑 Consigne finale : Réponds de manière NATURELLE, HUMAINE, IMPRÉVISIBLE en {nom_langue}. 
1 à 3 phrases maximum. Pas de salutation. Pas de question systématique. Sois toi-même.
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
                        "messages": [
                            {"role": "system", "content": "Tu es un geek passionné de tech. Tu réponds de manière naturelle, sans salutations inutiles. Tu utilises le tutoiement. Tu évites les questions systématiques."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 120,
                        "temperature": 0.95  # Plus créatif
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

    # Fallback ultime (avec personnalité)
    reponses_fallback = [
        "Ah ouais, je vois ce que tu veux dire. J'ai eu la même réflexion la semaine dernière.",
        "Intéressant. J'ai testé un truc similaire sur mon Redmi, ça marche pas mal.",
        "C'est clair, on est sur la même longueur d'onde. T'as pensé à checké XDA ?",
        "Je valide. T'as raison, c'est un bon plan. J'ai fait pareil avec mon G5S."
    ]
    return random.choice(reponses_fallback)