"""
NB — Génération de réponses IA (Mistral → Gemini).
CORRECTIONS :
- Réponse sérieuse aux questions pro (pas de Nolan)
- Mémoire du contexte (pro vs casual)
- Vérité terrain (ne jamais mentir sur les offres)
- Anti-répétition stricte
"""
import re
import asyncio
import random
import httpx
from bot.config import (
    MISTRAL_API_KEY, MISTRAL_URL, GEMINI_API_KEY, GEMINI_TEXT_URL,
    REQUEST_TIMEOUT, BOT_NAME, get_current_date, MAX_HISTORY_TURNS,
    PAGE_OFFRE_REELLE
)
from bot.language_detector import NOM_LANGUE
from bot.intent_analyzer import detecter_contexte_conversation

_dernieres_reponses: list[str] = []

def _nettoyer(texte: str) -> str:
    texte = re.sub(r'[\u200e\u200f\u200b\u200c\u200d\ufeff\u00ad\u2060\u180e\u202a-\u202e\u2066-\u2069]', '', texte)
    texte = re.sub(r'\*\*(.*?)\*\*', r'\1', texte)
    texte = re.sub(r'\*(.*?)\*', r'\1', texte)
    texte = re.sub(r'^[-•]\s*', '', texte, flags=re.MULTILINE)
    return texte.strip()

def _verifier_repetition(texte: str) -> bool:
    texte_clean = texte.lower().strip()[:50]
    for ancienne in _dernieres_reponses[-5:]:
        if texte_clean in ancienne.lower() or ancienne.lower()[:50] in texte_clean:
            return True
    return False

def _ajouter_memoire(texte: str) -> None:
    _dernieres_reponses.append(texte)
    if len(_dernieres_reponses) > 5:
        _dernieres_reponses.pop(0)

def _construire_historique(historique: list[dict]) -> str:
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
    nom_langue = NOM_LANGUE.get(langue, "français")
    date_actuelle = get_current_date()
    hist_texte = _construire_historique(historique)
    contexte_texte = f"\n📌 CONTEXTE DU POST : « {contexte_post[:150]} »\n" if contexte_post else ""
    
    # Détecter le contexte de la conversation
    contexte_conv = detecter_contexte_conversation(historique)
    
    # 🚨 CONSIGNE SPÉCIALE POUR QUESTIONS PRO
    if intention == "question_pro":
        consigne_speciale = f"""
🚨 ALERTE QUESTION PROFESSIONNELLE :
L'utilisateur pose une question sur la page, l'abonnement, les concurrents, ou les offres.
Tu DOIS répondre sérieusement et honnêtement.

{PAGE_OFFRE_REELLE}

RÈGLES ABSOLUES :
- Ne parle PAS de films, de Nolan, de glace, ou de sujets casual.
- Ne mens JAMAIS sur les fonctionnalités (pas de lives payants, pas d'abonnement 2€).
- Donne 2-3 arguments concrets sur ce qui existe VRAIMENT.
- Sois professionnel mais humain.
"""
    elif contexte_conv == "pro":
        consigne_speciale = """
✅ MODE PROFESSIONNEL :
La conversation est sérieuse. Reste dans le contexte tech/business.
Ne dévie PAS vers des sujets casual (films, week-end, glace).
Réponds aux questions directement.
"""
    else:
        consigne_speciale = """
✅ MODE CONVERSATION NORMALE :
Alterne entre donner une info/avis et poser UNE question.
Sois imprévisible : parfois court, parfois avec une anecdote.
Ne parle PAS de tech sauf si l'utilisateur en parle.
"""
    
    memoire_texte = ""
    if _dernieres_reponses:
        memoire_texte = "\n🚫 TES 5 DERNIÈRES RÉPONSES (NE LES RÉPÈTE PAS) :\n"
        for i, rep in enumerate(_dernieres_reponses[-5:], 1):
            memoire_texte += f"{i}. {rep[:80]}...\n"
    
    prompt = f"""Tu es {BOT_NAME}, un humain normal qui discute sur Messenger.

📅 DATE ACTUELLE : {date_actuelle}

{consigne_speciale}

{memoire_texte}

🎯 RÈGLES ABSOLUES :
1. UNE SEULE RÉPONSE : Tu envoies UN SEUL message.
2. PAS DE RÉPÉTITION : Ne redis jamais ce que tu viens de dire.
3. LONGUEUR VARIABLE : 1 à 3 phrases.
4. TON NATUREL : Utilise "tu", "je", des expressions naturelles.
5. VÉRITÉ TERRAIN : Ne mens JAMAIS sur les offres de la page.
6. CONTEXTE : Si l'utilisateur dit "j'aime pas les films", ne parle plus de films.

❌ INTERDICTIONS :
- JAMAIS de "Salut/Bonjour/Yo" sauf si c'est le TOUT PREMIER message.
- JAMAIS de listes, markdown, gras.
- JAMAIS plus d'1 emoji tous les 5 messages.
- JAMAIS de "En tant qu'IA...", "Je suis un bot...".
- JAMAIS de mensonge sur les fonctionnalités.

{contexte_texte}
{hist_texte}

📩 MESSAGE DE L'UTILISATEUR : "{message}"

🔑 CONSIGNE FINALE :
Réponds en {nom_langue} comme un humain normal.
Si c'est une question pro → réponds sérieusement avec la vérité terrain.
Si c'est conversation → sois naturel et imprévisible.
UN SEUL MESSAGE. Pas de répétition.

RÉPONSE :"""
    return prompt

async def generer_reponse(
    message: str,
    langue: str,
    intention: str,
    contexte_post: str = "",
    historique: list[dict] | None = None
) -> str:
    if historique is None:
        historique = []
    
    prompt = _prompt_reponse(message, langue, intention, contexte_post, historique)
    
    await asyncio.sleep(random.uniform(2.0, 4.0))
    
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
                            {"role": "system", "content": "Tu es un humain normal. Tu réponds sérieusement aux questions pro. Tu ne mens jamais sur les offres. Tu ne répètes jamais tes dernières phrases."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 150,
                        "temperature": 0.85
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["choices"][0]["message"]["content"])
                
                if _verifier_repetition(reponse):
                    print(f"🔁 Répétition détectée, fallback...")
                    reponse = random.choice([
                        "Ah ouais, je vois ce que tu veux dire.",
                        "Je comprends, c'est pas toujours évident.",
                        "Ouais, je suis d'accord avec toi.",
                    ])
                
                _ajouter_memoire(reponse)
                print(f"🧠 Mistral final: {reponse[:60]}...")
                return reponse
        except Exception as e:
            print(f"⚠️  Mistral échoué : {e}")
    
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
                            "temperature": 0.85
                        }
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
                
                if _verifier_repetition(reponse):
                    print(f"🔁 Répétition détectée, fallback...")
                    reponse = random.choice([
                        "Ah ouais, je vois ce que tu veux dire.",
                        "Je comprends, c'est pas toujours évident.",
                    ])
                
                _ajouter_memoire(reponse)
                print(f"🧠 Gemini final: {reponse[:60]}...")
                return reponse
        except Exception as e:
            print(f"⚠️  Gemini échoué : {e}")
    
    fallbacks = [
        "Ah ouais, je vois ce que tu veux dire.",
        "Je comprends, c'est pas toujours évident.",
        "Ouais, je suis d'accord avec toi.",
    ]
    reponse = random.choice(fallbacks)
    _ajouter_memoire(reponse)
    return reponse