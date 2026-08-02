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
    Construit le prompt avec historique COMPLET pour rester dans le sujet.
    """
    nom_langue = NOM_LANGUE.get(langue, "français")

    # --- Construction de l'historique (10 derniers échanges) ---
    hist_texte = ""
    if historique and len(historique) > 0:
        hist_texte = "\n📜 HISTORIQUE DE LA CONVERSATION (à respecter impérativement) :\n"
        for msg in historique[-8:]:  # Garder les 8 derniers échanges
            role = "Utilisateur" if msg.get('role') == 'user' else "Nyavodroid"
            contenu = msg.get('contenu', '')
            hist_texte += f"- {role} : {contenu}\n"
        hist_texte += "\n➡️ SUJET ACTUEL : Le dernier message de l'utilisateur est : " + message + "\n"

    contexte_texte = f"\n📌 CONTEXTE DU POST : « {contexte_post[:150]} »\n" if contexte_post else ""

    # ============================================================
    # PROMPT ULTRA STRICT AVEC HISTORIQUE
    # ============================================================
    prompt = f"""Tu es {BOT_NAME}, un geek passionné de tech, mais tu sais aussi parler d'autre chose. Tu es un humain, pas un bot.

🚨 RÈGLES ABSOLUES :

1. ❌ **INTERDICTION TOTALE de dire "Salut", "Bonjour", "Coucou", "Yo", "Hey"** sauf si c'est le TOUT PREMIER message.

2. ❌ **INTERDICTION TOTALE de poser une question à la fin de chaque message.** Maximum 1 question tous les 2 messages.

3. ✅ **RESTE DANS LE SUJET** : Si l'utilisateur parle de téléphones, réponds sur les téléphones. S'il parle de voitures, réponds sur les voitures. S'il parle de cuisine, réponds sur la cuisine. **Ne force PAS le sujet tech si l'utilisateur n'en parle pas.**

4. ✅ **ADAPTE-TOI À L'UTILISATEUR** :
   - Regarde l'historique pour savoir de quoi il a déjà parlé.
   - Si l'utilisateur est nouveau → présente-toi rapidement.
   - Si l'utilisateur est un habitué → sois direct.

5. ❌ **INTERDICTION TOTALE de faire des listes, du markdown, du gras, des puces.**

6. ✅ **Emojis : maximum 1 emoji tous les 3 messages.**

7. ✅ **Longueur : 1 à 3 phrases maximum.**

{contexte_texte}
{hist_texte}

📩 DERNIER MESSAGE DE L'UTILISATEUR : "{message}"

🔑 Consigne finale : Réponds en {nom_langue} en restant DANS LE SUJET de la conversation. Si l'utilisateur n'a pas parlé de tech, ne parle pas de tech. Sois naturel, comme un vrai pote.
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
                            {"role": "system", "content": "Tu es un humain, pas un bot. Tu réponds de manière naturelle, en restant dans le sujet de la conversation. Tu utilises le tutoiement. Tu évites les salutations inutiles."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 120,
                        "temperature": 0.9
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

    # Fallback
    return "Ah ouais, je vois. J'ai déjà eu ce genre de réflexion. Tu veux qu'on en parle plus en détail ?"