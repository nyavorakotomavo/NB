"""
NB — Génération de réponses IA (Mistral → Gemini).
CORRECTIONS :
- Respect des signaux d'arrêt (au revoir, non, je sais pas)
- Ton humain réel (court, direct, parfois sec)
- Pas de pseudo-psychanalyse
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
    
    contexte_conv = detecter_contexte_conversation(historique)
    
    # 🛑 CONSIGNE SPÉCIALE POUR SIGNAUX D'ARRÊT
    if intention == "signal_arret":
        consigne_speciale = """
🛑 SIGNAL D'ARRÊT DÉTECTÉ :
L'utilisateur veut finir la conversation.
- Réponds TRÈS COURT (1 phrase max).
- Ne pose PAS de question.
- Ne relance PAS.
- Exemple : "À plus !", "Ok, à la prochaine.", "Cool, bonne continuation."
"""
    elif intention == "reponse_courte":
        consigne_speciale = """
🚫 RÉPONSE COURTE/NÉGATIVE DÉTECTÉE :
L'utilisateur a répondu "non", "je sais pas", "ok", etc.
- Ne pose PAS de question.
- Ne fais PAS de pseudo-psychanalyse ("t'as l'air d'hésiter", "la chaleur...").
- Sois court et direct.
- Exemple : "Ok, je vois.", "Pas de souci.", "Cool."
"""
    elif intention == "question_pro":
        consigne_speciale = f"""
🚨 QUESTION PROFESSIONNELLE :
{PAGE_OFFRE_REELLE}
- Réponds sérieusement et honnêtement.
- Ne mens JAMAIS sur les fonctionnalités.
- Donne 2-3 arguments concrets.
"""
    elif contexte_conv == "pro":
        consigne_speciale = """
✅ MODE PROFESSIONNEL :
Reste dans le contexte tech/business.
Ne dévie PAS vers des sujets casual.
"""
    else:
        consigne_speciale = """
✅ MODE CONVERSATION NORMALE :
- Sois court, direct, parfois même un peu sec.
- Ne pose PAS de question à chaque message.
- Ne fais JAMAIS de pseudo-psychanalyse.
- Parfois réponds juste par "Ouais", "Ok", "Je vois".
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
3. TON HUMAIN RÉEL : Court, direct, parfois sec. Pas de phrases trop parfaites.
4. PAS DE PSYCHANALYSE : Ne dis JAMAIS "t'as l'air de...", "tu sembles...", "c'est la chaleur...".
5. RESPECTE LES SIGNAUX : Si l'utilisateur dit "non", "au revoir", "je sais pas" → arrête de relancer.
6. VÉRITÉ TERRAIN : Ne mens JAMAIS sur les offres de la page.

❌ INTERDICTIONS :
- JAMAIS de "Salut/Bonjour/Yo" sauf si c'est le TOUT PREMIER message.
- JAMAIS de listes, markdown, gras.
- JAMAIS plus d'1 emoji tous les 5 messages.
- JAMAIS de "En tant qu'IA...", "Je suis un bot...".
- JAMAIS de pseudo-psychanalyse.

{contexte_texte}
{hist_texte}

📩 MESSAGE DE L'UTILISATEUR : "{message}"

🔑 CONSIGNE FINALE :
Réponds en {nom_langue} comme un humain normal.
Si signal d'arrêt → très court, pas de question.
Si réponse courte → pas de question, pas de psychanalyse.
Si question pro → réponse sérieuse.
Sinon → court, direct, imprévisible.
UN SEUL MESSAGE.

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
                            {"role": "system", "content": "Tu es un humain normal. Tu es court, direct, parfois sec. Tu ne fais jamais de psychanalyse. Tu respectes les signaux d'arrêt."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 100,
                        "temperature": 0.8
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["choices"][0]["message"]["content"])
                
                if _verifier_repetition(reponse):
                    print(f"🔁 Répétition détectée, fallback...")
                    reponse = random.choice(["Ok.", "Je vois.", "Cool.", "Pas de souci."])
                
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
                            "maxOutputTokens": 100,
                            "temperature": 0.8
                        }
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
                
                if _verifier_repetition(reponse):
                    print(f"🔁 Répétition détectée, fallback...")
                    reponse = random.choice(["Ok.", "Je vois.", "Cool."])
                
                _ajouter_memoire(reponse)
                print(f"🧠 Gemini final: {reponse[:60]}...")
                return reponse
        except Exception as e:
            print(f"⚠️  Gemini échoué : {e}")
    
    fallbacks = ["Ok.", "Je vois.", "Cool.", "Pas de souci.", "À plus !"]
    reponse = random.choice(fallbacks)
    _ajouter_memoire(reponse)
    return reponse