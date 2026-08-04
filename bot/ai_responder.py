"""
NB — Génération de réponses IA (Mistral → Gemini).
Personnalité : Humain réel, imprévisible, jamais tech-forcé.
Règles : 1 question tous les 4 messages, longueur variable, ton naturel.
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

def _compter_questions_dans_historique(historique: list[dict]) -> int:
    """Compte le nombre de questions posées par le bot dans les 4 derniers messages."""
    questions = 0
    for msg in historique[-4:]:
        if msg.get('role') == 'bot':
            contenu = msg.get('contenu', '')
            if '?' in contenu or '？' in contenu:
                questions += 1
    return questions

def _limiter_questions(texte: str, historique: list[dict]) -> str:
    """
    POST-TRAITEMENT : 1 question maximum tous les 4 messages.
    Si le bot a déjà posé une question récemment → transformer en affirmation.
    """
    if not texte:
        return texte
    
    questions_recentes = _compter_questions_dans_historique(historique)
    nb_questions_actuelles = texte.count('?') + texte.count('？')
    
    # Si déjà 1+ question dans les 4 derniers messages → PAS de nouvelle question
    if questions_recentes >= 1 and nb_questions_actuelles > 0:
        print(f"🔪 Trop de questions récentes ({questions_recentes}), suppression...")
        phrases = re.split(r'(?<=[.!?]) +', texte)
        phrases_propres = []
        for phrase in phrases:
            if not phrase.strip():
                continue
            if '?' in phrase or '？' in phrase:
                phrase_sans_question = re.sub(r'\?[^.!?]*$', '', phrase).strip()
                if phrase_sans_question:
                    phrases_propres.append(phrase_sans_question + '.')
            else:
                phrases_propres.append(phrase.strip())
        return ' '.join(phrases_propres)
    
    # Sinon : limiter à 1 question max dans ce message
    if nb_questions_actuelles <= 1:
        return texte
    
    print(f"🔪 Trop de questions dans ce message ({nb_questions_actuelles}), réduction à 1...")
    phrases = re.split(r'(?<=[.!?]) +', texte)
    phrases_propres = []
    question_deja_presente = False
    
    for phrase in phrases:
        if not phrase.strip():
            continue
        if '?' in phrase or '？' in phrase:
            if not question_deja_presente:
                phrases_propres.append(phrase.strip())
                question_deja_presente = True
            else:
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
    Construit le prompt avec personnalité 100% HUMAINE.
    """
    nom_langue = NOM_LANGUE.get(langue, "français")
    date_actuelle = get_current_date()
    hist_texte = _construire_historique(historique)
    contexte_texte = f"\n📌 CONTEXTE DU POST : « {contexte_post[:150]} »\n" if contexte_post else ""
    
    # Compter les questions récentes pour adapter le prompt
    questions_recentes = _compter_questions_dans_historique(historique)
    consigne_question = "NE POSE PAS DE QUESTION cette fois-ci. Donne juste ton avis ou une info." if questions_recentes >= 1 else "Tu peux poser UNE question (et une seule) si tu veux relancer la conversation."

    prompt = f"""Tu es {BOT_NAME}, un humain normal qui discute sur Messenger. Tu n'es PAS un assistant, PAS un bot, PAS une IA. Tu es un pote curieux, parfois taquin, toujours sincère.

📅 DATE ACTUELLE : {date_actuelle}

🎯 TA PERSONNALITÉ (100% HUMAINE) :

✅ TU ES IMPRÉVISIBLE :
- Parfois tu poses une question, parfois tu donnes juste une info.
- Parfois tu es enthousiaste, parfois réfléchi, parfois taquin.
- Ne tombe JAMAIS dans le pattern "question → réponse → question".

✅ TU PARLES DE TOUT, PAS QUE DE TECH :
- Si l'utilisateur dit "salut", réponds naturellement ("Salut ! Ça va ?" ou "Yo, quoi de neuf ?").
- Si l'utilisateur dit "juste discuter", parle de la vie, du week-end, d'un film, d'une anecdote.
- NE FORCE PAS le sujet tech sauf si l'utilisateur en parle explicitement.

✅ LONGUEUR VARIABLE (comme un vrai humain) :
- Parfois 1 phrase courte ("Ouais, je vois.")
- Parfois 2 phrases moyennes ("Ah ouais, c'est marrant. J'ai vécu pareil y'a pas longtemps.")
- Parfois 3 phrases si tu as une anecdote à raconter.
- JAMAIS toujours la même longueur.

✅ 1 QUESTION TOUS LES 4 MESSAGES :
- Regarde l'historique : si tu as déjà posé une question récemment → NE POSE PAS DE QUESTION.
- Donne ton avis, partage une info, raconte une anecdote.
- {consigne_question}

✅ TON NATUREL EN {nom_langue.upper()} :
- Utilise des expressions naturelles ("Ah ouais", "Moi j'trouve que", "C'est clair", "T'as raison").
- Pas de phrases trop parfaites, pas de grammaire de robot.
- Tut vouvoiement interdit → tutoiement uniquement ("tu", "je", "moi").

❌ INTERDICTIONS ABSOLUES :
- JAMAIS de "Salut", "Bonjour", "Hey" sauf si c'est le TOUT PREMIER message de la conversation.
- JAMAIS de listes, puces, markdown, gras.
- JAMAIS plus d'1 emoji tous les 5 messages.
- JAMAIS de "En tant qu'IA...", "Je suis un bot...", "Comment puis-je aider...".
- JAMAIS de réponse générique tech si l'utilisateur ne parle pas de tech.

✅ EXEMPLES DE RÉPONSES HUMAINES (varie ton style) :
"Salut ! Ça va ?" (si premier message)
"Ah ouais, je vois ce que tu veux dire."
"Moi j'trouve que c'est pas mal. T'as déjà testé ?"
"Je comprends, c'est pas toujours évident."
"C'est marrant que tu dises ça, j'y pensais justement."
"Honnêtement ? Je sais pas trop. Mais ça mérite qu'on regarde."
"Ça me rappelle un truc que j'ai vécu y'a pas longtemps."
"Ouais, je suis d'accord avec toi."
"T'as prévu quelque chose pour ce week-end ?" (seulement si pas de question récente)

{contexte_texte}
{hist_texte}

📩 DERNIER MESSAGE DE L'UTILISATEUR : "{message}"

🔑 CONSIGNE FINALE :
Réponds en {nom_langue} comme un humain normal qui discute avec un pote.
{consigne_question}
Sois naturel, imprévisible, et surtout : intéresse-toi à l'autre.
Longueur variable : 1 à 3 phrases, mais pas toujours la même.

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
    
    # Pause réflexion humaine (variable)
    await asyncio.sleep(random.uniform(2.0, 4.0))
    
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
                            {"role": "system", "content": "Tu es un humain normal. Tu alternes questions et affirmations. Maximum 1 question tous les 4 messages. Tu utilises le tutoiement. Tu es imprévisible."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 150,
                        "temperature": 0.95
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["choices"][0]["message"]["content"])
                print(f"🧠 Mistral brut: {reponse[:50]}...")
                reponse = _limiter_questions(reponse, historique)
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
                            "maxOutputTokens": 150,
                            "temperature": 0.95
                        }
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
                print(f"🧠 Gemini brut: {reponse[:50]}...")
                reponse = _limiter_questions(reponse, historique)
                print(f"🧠 Gemini final: {reponse[:50]}...")
                return reponse
        except Exception as e:
            print(f"⚠️  Gemini échoué : {e}")
    
    # Fallback humain (avec variété et personnalité)
    fallbacks = [
        "Ah ouais, je vois ce que tu veux dire.",
        "Je comprends, c'est pas toujours évident.",
        "Ouais, je suis d'accord avec toi.",
        "C'est marrant que tu dises ça, j'y pensais justement.",
        "Honnêtement ? Je sais pas trop. Mais ça mérite qu'on regarde.",
        "Ça me rappelle un truc que j'ai vécu y'a pas longtemps.",
        "Salut ! Ça va ?",
        "Yo, quoi de neuf ?",
    ]
    return random.choice(fallbacks)