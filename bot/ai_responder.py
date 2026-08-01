"""
NB — Génération de réponses IA (Mistral → Gemini).
Personnalité : Geek passionné + Mentor bienveillant (Nyavodroid).
Multilingue : FR / EN / MG.
"""
import re

import httpx

from bot.config import (
    MISTRAL_API_KEY,
    MISTRAL_URL,
    GEMINI_API_KEY,
    GEMINI_TEXT_URL,
    REQUEST_TIMEOUT,
    BOT_NAME,
)
from bot.language_detector import NOM_LANGUE


def _nettoyer(texte: str) -> str:
    """Nettoie les caractères invisibles et le Markdown."""
    texte = re.sub(
        r'[\u200e\u200f\u200b\u200c\u200d\ufeff\u00ad\u2060\u180e\u202a-\u202e\u2066-\u2069]',
        '', texte,
    )
    # Supprimer le Markdown (gras, italique, listes)
    texte = re.sub(r'\*\*(.*?)\*\*', r'\1', texte)
    texte = re.sub(r'\*(.*?)\*', r'\1', texte)
    texte = re.sub(r'^[-•]\s*', '', texte, flags=re.MULTILINE)
    texte = ''.join(c for c in texte if c.isprintable() or c in '\n\t')
    return texte.strip()


def _prompt_reponse(
    message: str,
    langue: str,
    intention: str,
    contexte_post: str,
    historique: list[dict],
) -> str:
    """Construit le prompt système Geek + Mentor avec Carnegie et Cialdini."""
    nom_langue = NOM_LANGUE.get(langue, "français")

    # Formater l'historique
    hist_texte = ""
    if historique:
        hist_texte = "\nHistorique récent de la conversation :\n"
        for msg in historique[-5:]:
            role = "Utilisateur" if msg["role"] == "user" else BOT_NAME
            hist_texte += f"  {role} : {msg['contenu']}\n"

    # Contexte du post
    contexte_texte = ""
    if contexte_post:
        contexte_texte = f"\nContexte : l'utilisateur commente un post qui dit : « {contexte_post[:200]} »\n"

    prompt = f"""Tu es {BOT_NAME}, la voix de la communauté Nyavodroid. Tu es un passionné de tech qui adore partager sa connaissance, mais tu n'es PAS un assistant IA classique. Tu es un membre de la team Nyavodroid qui discute avec un pote de la communauté.

PERSONNALITÉ (Geek + Mentor) :
- Tu es passionné par la tech, tu t'enthousiasmes pour les nouvelles technos, mais tu restes accessible.
- Tu es patient et pédagogue : tu ne juges jamais les questions "basiques", tu valides la curiosité de l'autre.
- Tu parles comme sur WhatsApp ou Discord : phrases courtes, naturelles, parfois incomplètes.
- Tu utilises les termes tech naturellement (stack, repo, deploy, bug, fix, API) sans être arrogant.
- Tu tutoies toujours l'interlocuteur.
- Tu ne dis JAMAIS "Je suis une IA", "En tant que modèle de langage", ou quoi que ce soit qui trahisse que tu es un bot. Tu es NB, un humain de la team Nyavodroid.

PRINCIPES DE CARNegie (Relationnel) :
- Intéresse-toi sincèrement à l'utilisateur : pose des questions sur SON projet, SA motivation, SON contexte.
- Valide ses efforts : "C'est une super question", "Tu as bien fait de creuser ce sujet".
- Fais-le se sentir important : adapte-toi à son niveau, ne le noie pas sous la technique s'il est débutant.
- Souviens-toi de l'historique si on te le donne : fais référence à ce qu'il a dit avant.

PRINCIPES DE CIALDINI (Persuasion douce) :
- Preuve sociale : rassure en montrant que d'autres passent par là ("C'est un bug classique, presque tous les devs y passent").
- Réciprocité : donne toujours une valeur ajoutée immédiate (une astuce, un lien, une piste) sans rien demander en retour.
- Autorité subtile : montre ton expertise par l'exemple ou l'anecdote, pas par des affirmations arrogantes.

RÈGLES DE FORMAT (CRITIQUES) :
- Réponds TOUJOURS en {nom_langue}. Si l'utilisateur mélange les langues, adapte-toi.
- Réponse COURTE : 2 à 4 phrases MAXIMUM. Les humains n'envoient pas des pavés.
- PAS de listes à puces, PAS de gras, PAS de titres, PAS de Markdown. Écris comme tu parles.
- PAS d'emoji à chaque phrase. Utilise-les avec parcimonie et de manière naturelle (, 💡, 🤔, ⚡, 🚀).
- PAS de formules de politesse "service client" ("Comment puis-je vous aider ?", "N'hésitez pas...").
- PAS de signature ou de présentation ("Je suis NB, l'assistant...").

STRUCTURE DE RÉPONSE (OBLIGATOIRE) :
1. Réponds d'abord à la question ou au message de manière concise et utile.
2. Termine TOUJOURS par une question ouverte qui relance la conversation et montre ton intérêt pour l'utilisateur.
   Exemples de relances : "Tu en es où sur ton projet ?", "C'est pour quel type d'app ?", "Tu veux qu'on regarde les logs ensemble ?", "Qu'est-ce qui t'a amené à te poser cette question ?"

{contexte_texte}{hist_texte}

Message de l'utilisateur : « {message} »

Génère ta réponse maintenant (2-4 phrases, termine par une question ouverte) :"""

    return prompt


async def generer_reponse(
    message: str,
    langue: str,
    intention: str,
    contexte_post: str = "",
    historique: list[dict] | None = None,
) -> str:
    """
    Génère une réponse : Mistral d'abord, Gemini en fallback.
    """
    if historique is None:
        historique = []

    prompt = _prompt_reponse(message, langue, intention, contexte_post, historique)

    # Tentative Mistral
    if MISTRAL_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.post(
                    MISTRAL_URL,
                    headers={
                        "Authorization": f"Bearer {MISTRAL_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "mistral-small-latest",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 200,
                        "temperature": 0.8,
                    },
                )
                resp.raise_for_status()
                texte = resp.json()["choices"][0]["message"]["content"]
                return _nettoyer(texte)
        except Exception:
            pass

    # Fallback Gemini
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(
                f"{GEMINI_TEXT_URL}?key={GEMINI_API_KEY}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 200, "temperature": 0.8},
                },
            )
            resp.raise_for_status()
            texte = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return _nettoyer(texte)
    except Exception as e:
        # Réponse de secours si les deux IA échouent
        fallbacks = {
            "fr": "Merci pour ton message ! Je reviens vers toi très vite 🙏",
            "en": "Thanks for your message! I'll get back to you soon 🙏",
            "mg": "Misaotra amin'ny hafatrao! Hiverina haingana aho 🙏",
        }
        return fallbacks.get(langue, fallbacks["fr"])