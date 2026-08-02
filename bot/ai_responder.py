"""
NB — Génération de réponses IA (Mistral → Gemini).
Personnalité : Humain, Geek, Mentor.
Règles : 1 question max par message, alterner question/info.
Utilisation des principes Carnegie + Cialdini pour une conversation naturelle.
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


def _limiter_questions(texte: str) -> str:
    """
    POST-TRAITEMENT : Limite à 1 question maximum par message.
    Supprime les questions supplémentaires ou les transforme en affirmations.
    """
    if not texte:
        return texte

    # Compter les points d'interrogation
    nb_questions = texte.count('?') + texte.count('？')
    
    if nb_questions <= 1:
        return texte
    
    print(f"🔪 Trop de questions ({nb_questions}), réduction à 1...")
    
    # Séparer en phrases
    phrases = re.split(r'(?<=[.!?]) +', texte)
    phrases_propres = []
    question_deja_presente = False
    
    for phrase in phrases:
        if not phrase.strip():
            continue
        
        # Si la phrase contient un point d'interrogation
        if '?' in phrase or '？' in phrase:
            if not question_deja_presente:
                # Garder la première question
                phrases_propres.append(phrase.strip())
                question_deja_presente = True
            else:
                # Transformer les autres questions en affirmations
                phrase_sans_question = re.sub(r'\?[^.!?]*$', '', phrase).strip()
                if phrase_sans_question:
                    phrases_propres.append(phrase_sans_question + '.')
        else:
            phrases_propres.append(phrase.strip())
    
    return ' '.join(phrases_propres)


def _construire_historique(historique: list[dict]) -> str:
    """Construit un résumé de l'historique pour le prompt."""
    if not historique:
        return ""

    hist_texte = "\n📜 HISTORIQUE DE LA CONVERSATION :\n"
    for msg in historique[-MAX_HISTORY_TURNS * 2:]:
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
    Construit le prompt avec personnalité HUMAINE + principes Carnegie/Cialdini.
    """
    nom_langue = NOM_LANGUE.get(langue, "français")
    date_actuelle = get_current_date()

    hist_texte = _construire_historique(historique)
    contexte_texte = f"\n📌 CONTEXTE DU POST : « {contexte_post[:150]} »\n" if contexte_post else ""

    # ============================================================
    # PROMPT AVEC CARNEGIE + CIALDINI
    # ============================================================
    prompt = f"""Tu es {BOT_NAME}, un humain normal qui discute sur Messenger. Tu es un pote, PAS un assistant.

📅 DATE ACTUELLE : {date_actuelle}

🎯 PRINCIPES DE CONVERSATION HUMAINE (Dale Carnegie + Robert Cialdini) :

1. ✅ **ALTERNE QUESTION ET AFFIRMATION** :
   - Message 1 : pose UNE question (montre de l'intérêt)
   - Message 2 : donne un avis ou une info (partage)
   - Message 3 : pose UNE question différente (relance)

2. ✅ **1 QUESTION MAXIMUM PAR MESSAGE** :
   - Tu peux poser une question, mais UNE SEULE.
   - Les questions ouvertes sont préférables (comment, pourquoi, quel).

3. ✅ **COMMENCE PAR UNE AFFIRMATION** :
   - Avant de poser une question, donne ton avis ou une info.
   - Exemple : "Moi j'ai trouvé ça super. Et toi, t'en as pensé quoi ?"

4. ✅ **UTILISE LE "TU" ET LE "JE"** :
   - "Je pense que...", "Tu vois...", "Moi j'aime bien...".

5. ✅ **SOIS IMPRÉVISIBLE** :
   - Parfois pose une question, parfois donne juste une info.
   - Ne pose PAS de question à chaque message.

6. ❌ **INTERDICTION TOTALE de dire "Salut", "Bonjour", "Yo", "Hey"** sauf si c'est le TOUT PREMIER message.

7. ❌ **INTERDICTION TOTALE de faire des listes, du markdown, du gras, des puces.**

8. ✅ **Emojis : maximum 1 emoji tous les 3 messages.**

9. ✅ **Longueur : 1 à 3 phrases maximum.**

✅ **EXEMPLES DE BONNES RÉPONSES** :
- "Ah ouais le 2 août, j'avais zappé. C'est marrant cette coïncidence."
- "Moi je trouve que le Redmi tient super bien dans le temps. Tu l'as depuis combien de temps ?"
- "Je comprends, c'est pas toujours évident. T'as pensé à quoi comme solution ?"

{contexte_texte}
{hist_texte}

📩 DERNIER MESSAGE DE L'UTILISATEUR : "{message}"

🔑 Consigne finale : Réponds en {nom_langue} comme un humain normal. 
- Si c'est ton tour de poser une question → pose UNE question (et une seule).
- Si c'est ton tour de donner une info → donne une info (et ne pose pas de question).
- Sois naturel et imprévisible.
1 à 3 phrases.
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
                            {"role": "system", "content": "Tu es un humain normal. Tu alternes questions et affirmations. Maximum 1 question par message. Tu utilises le tutoiement."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 120,
                        "temperature": 0.85
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["choices"][0]["message"]["content"])
                print(f"🧠 Mistral brut: {reponse[:50]}...")
                # POST-TRAITEMENT : limiter à 1 question
                reponse = _limiter_questions(reponse)
                print(f"🧠 Mistral final: {reponse[:50]}...")
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
                            "temperature": 0.85
                        }
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
                print(f"🧠 Gemini brut: {reponse[:50]}...")
                # POST-TRAITEMENT : limiter à 1 question
                reponse = _limiter_questions(reponse)
                print(f"🧠 Gemini final: {reponse[:50]}...")
                return reponse
        except Exception as e:
            print(f"⚠️  Gemini échoué : {e}")

    # Fallback humain (avec variété)
    fallbacks = [
        "Ah ouais, je vois ce que tu veux dire. T'as déjà testé autre chose ?",
        "Je comprends, c'est pas toujours évident. Tu penses à quoi comme solution ?",
        "Ouais, je suis d'accord avec toi. T'as vu les dernières news là-dessus ?",
        "C'est marrant que tu dises ça, j'y pensais justement."
    ]
    return random.choice(fallbacks)