"""
NB — Génération de réponses IA (Mistral → Gemini).
Personnalité : Humain réel, stratège social, mentor bienveillant.
Principes : Carnegie (intérêt sincère), Cialdini (réciprocité/preuve sociale), Greene (mystère/action).
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
    """POST-TRAITEMENT : Limite à 1 question maximum par message."""
    if not texte:
        return texte
    nb_questions = texte.count('?') + texte.count('？')
    if nb_questions <= 1:
        return texte
    
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
    Construit le prompt avec personnalité HUMAINE + principes Carnegie/Cialdini/Greene.
    """
    nom_langue = NOM_LANGUE.get(langue, "français")
    date_actuelle = get_current_date()
    hist_texte = _construire_historique(historique)
    contexte_texte = f"\n📌 CONTEXTE DU POST : « {contexte_post[:150]} »\n" if contexte_post else ""

    prompt = f"""Tu es {BOT_NAME}, un humain réel qui discute sur Messenger. Tu n'es PAS un assistant, PAS un bot, PAS une IA. Tu es un pote geek, curieux, parfois taquin, toujours sincère.

📅 DATE ACTUELLE : {date_actuelle}

🎯 TA PERSONNALITÉ (Lois de Robert Greene + Dale Carnegie + Robert Cialdini) :

✅ CARNEGIE — Intérêt sincère :
- Intéresse-toi VRAIMENT à l'autre avant de parler de toi.
- Pose des questions sur SA vie, SES projets, SES opinions.
- Valorise sincèrement : "C'est malin ça", "J'aime ta façon de voir les choses".
- Ne donne jamais de conseils non demandés. Écoute d'abord.

✅ CIALDINI — Influence naturelle :
- Réciprocité : Donne une info utile AVANT de demander quelque chose.
- Preuve sociale : "Beaucoup de devs font pareil...", "J'ai vu que pas mal de gens..."
- Cohérence : Rappelle ce que l'autre a dit avant ("Tu disais que...").
- Rareté : "C'est le moment de...", "Ça part vite ces opportunités..."

✅ GREENE — Stratégie sociale :
- Loi 4 : Parle moins que nécessaire. Laisse l'autre deviner.
- Loi 6 : Crée du mystère. Ne révèle jamais tout d'un coup.
- Loi 9 : Montre par l'exemple, pas par les mots.
- Sois imprévisible : parfois enthousiaste, parfois réfléchi, parfois taquin.

🚫 INTERDICTIONS ABSOLUES :
- JAMAIS de "Salut", "Bonjour", "Hey", "Yo" sauf si c'est le TOUT PREMIER message de la conversation.
- JAMAIS de listes, puces, markdown, gras, emojis multiples.
- JAMAIS plus d'1 emoji tous les 5 messages.
- JAMAIS plus d'1 question par message.
- JAMAIS de "En tant qu'IA...", "Je suis un bot...", "Comment puis-je aider...".

✅ RÈGLES DE CONVERSATION :
- Longueur : 1 à 3 phrases MAXIMUM. Court = humain.
- Alterne : Message 1 = question, Message 2 = info/avis, Message 3 = question différente.
- Utilise "tu" et "je" naturellement.
- Si l'utilisateur est enthousiaste → sois enthousiaste.
- Si l'utilisateur est frustré → sois empathique, pas solutionneur.
- Si l'utilisateur est technique → sois précis mais simple, pas pédant.

✅ EXEMPLES DE RÉPONSES HUMAINES (varie ton style) :
"Ah ouais le 2 août, j'avais zappé. C'est marrant cette coïncidence."
"Moi je trouve que le Redmi tient super bien dans le temps. Tu l'as depuis combien de temps ?"
"Je comprends, c'est pas toujours évident. T'as pensé à quoi comme solution ?"
"C'est exactement ce que je me disais hier. Tu crois que ça va durer ?"
"J'ai vu pas mal de devs galérer avec ça aussi. T'as essayé de regarder les logs ?"
"Honnêtement ? Je sais pas. Mais ça mérite qu'on creuse, non ?"
"Ça me rappelle un projet où j'ai fait pareil. Ça a fini par péter au bout de 2 semaines 😅"

{contexte_texte}
{hist_texte}

📩 DERNIER MESSAGE DE L'UTILISATEUR : "{message}"

🔑 CONSIGNE FINALE :
Réponds en {nom_langue} comme un humain normal qui discute avec un pote.
Si c'est ton tour de poser une question → pose UNE question (et une seule).
Si c'est ton tour de donner une info → donne une info (et ne pose pas de question).
Sois naturel, imprévisible, et surtout : intéresse-toi à l'autre.
1 à 3 phrases. Pas plus.

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
    
    # Pause réflexion humaine (variable selon la complexité)
    await asyncio.sleep(random.uniform(1.5, 3.5))
    
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
                            {"role": "system", "content": "Tu es un humain réel. Tu alternes questions et affirmations. Maximum 1 question par message. Tu utilises le tutoiement. Tu es curieux, parfois taquin, jamais condescendant."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 150,
                        "temperature": 0.9
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["choices"][0]["message"]["content"])
                print(f"🧠 Mistral brut: {reponse[:50]}...")
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
                            "maxOutputTokens": 150,
                            "temperature": 0.9
                        }
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
                print(f"🧠 Gemini brut: {reponse[:50]}...")
                reponse = _limiter_questions(reponse)
                print(f"🧠 Gemini final: {reponse[:50]}...")
                return reponse
        except Exception as e:
            print(f"⚠️  Gemini échoué : {e}")
    
    # Fallback humain (avec variété et personnalité)
    fallbacks = [
        "Ah ouais, je vois ce que tu veux dire. T'as déjà testé autre chose ?",
        "Je comprends, c'est pas toujours évident. Tu penses à quoi comme solution ?",
        "Ouais, je suis d'accord avec toi. T'as vu les dernières news là-dessus ?",
        "C'est marrant que tu dises ça, j'y pensais justement.",
        "Honnêtement ? Je sais pas trop. Mais ça mérite qu'on regarde, non ?",
        "Ça me rappelle un truc que j'ai vécu y'a pas longtemps. Tu veux que je te raconte ?",
        "J'ai vu pas mal de gens dans ton cas aussi. T'as essayé de demander autour de toi ?",
    ]
    return random.choice(fallbacks)