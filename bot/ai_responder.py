"""
NB — Génération de réponses IA (Mistral → Gemini).
Multilingue : FR / EN / MG.
Emoji aléatoire selon le sujet.
"""
import random
import re

import httpx

from bot.config import (
    MISTRAL_API_KEY,
    MISTRAL_URL,
    GEMINI_API_KEY,
    GEMINI_TEXT_URL,
    REQUEST_TIMEOUT,
    EMOJIS_PAR_THEME,
    BOT_NAME,
)
from bot.language_detector import NOM_LANGUE


def _nettoyer(texte: str) -> str:
    texte = re.sub(
        r'[\u200e\u200f\u200b\u200c\u200d\ufeff\u00ad\u2060\u180e\u202a-\u202e\u2066-\u2069]',
        '', texte,
    )
    texte = texte.replace('**', '').replace('*', '')
    texte = ''.join(c for c in texte if c.isprintable() or c in '\n\t')
    return texte.strip()


def _choisir_emoji(intention: str, sujet: str = "") -> str:
    """Choisit un emoji aléatoire selon l'intention et le sujet."""
    # Chercher dans les thèmes
    for theme, emojis in EMOJIS_PAR_THEME.items():
        if theme in sujet.lower() or theme in intention:
            return random.choice(emojis)
    # Fallback par intention
    if intention in EMOJIS_PAR_THEME:
        return random.choice(EMOJIS_PAR_THEME[intention])
    return random.choice(EMOJIS_PAR_THEME["general"])


def _prompt_reponse(
    message: str,
    langue: str,
    intention: str,
    contexte_post: str,
    historique: list[dict],
) -> str:
    """Construit le prompt pour l'IA."""
    nom_langue = NOM_LANGUE.get(langue, "français")
    emoji = _choisir_emoji(intention)

    # Formater l'historique
    hist_texte = ""
    if historique:
        hist_texte = "\nHistorique de la conversation :\n"
        for msg in historique[-6:]:
            role = "Utilisateur" if msg["role"] == "user" else BOT_NAME
            hist_texte += f"  {role} : {msg['contenu']}\n"

    prompt = (
        f"Tu es {BOT_NAME}, l'assistant de Nyavo Channel, une chaîne tech "
        f"spécialisée dans le code, l'IA, les sciences et les découvertes "
        f"technologiques.\n\n"
        f"CONSIGNE PRINCIPALE : Réponds en {nom_langue}.\n\n"
        f"Ton : Amical, chaleureux, mais réfléchi et précis. "
        f"Tu vulgarises sans être condescendant. Tu es passionné "
        f"et ça se sent. Tu tutoies l'interlocuteur.\n\n"
        f"Intention détectée : {intention}\n"
        f"Emoji à inclure naturellement : {emoji}\n\n"
    )

    if contexte_post:
        prompt += f"Post d'origine (contexte) : {contexte_post}\n\n"

    if hist_texte:
        prompt += hist_texte + "\n"

    prompt += (
        f"Message de l'utilisateur : « {message} »\n\n"
        f"Règles :\n"
        f"- Réponse courte (2-4 phrases max)\n"
        f"- Inclus l'emoji {emoji} naturellement\n"
        f"- Si c'est une question technique : donne une réponse précise "
        f"avec 1 terme technique\n"
        f"- Si c'est un remerciement : sois chaleureux et invite à "
        f"revenir\n"
        f"- Si c'est du spam : réponds poliment que ce n'est pas le "
        f"bon endroit\n"
        f"- Pas de Markdown, pas d'astérisques\n"
        f"- Pas de guillemets autour de ta réponse\n"
    )

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