"""
NB — Génération de réponses IA (Mistral → Gemini).
CORRECTIONS MAJEURES :
- Anti-répétition stricte (mémoire des 5 derniers messages)
- Réponse directe obligatoire aux questions
- Un seul message par tour (pas de rafale)
- Mémoire conversationnelle réelle
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

# 🧠 Mémoire anti-répétition : stocke les 5 dernières réponses du bot
_dernieres_reponses: list[str] = []

def _nettoyer(texte: str) -> str:
    """Nettoie le texte des caractères invisibles et du formatage."""
    texte = re.sub(r'[\u200e\u200f\u200b\u200c\u200d\ufeff\u00ad\u2060\u180e\u202a-\u202e\u2066-\u2069]', '', texte)
    texte = re.sub(r'\*\*(.*?)\*\*', r'\1', texte)
    texte = re.sub(r'\*(.*?)\*', r'\1', texte)
    texte = re.sub(r'^[-•]\s*', '', texte, flags=re.MULTILINE)
    return texte.strip()

def _verifier_repetition(texte: str) -> bool:
    """Vérifie si le texte a déjà été envoyé récemment."""
    texte_clean = texte.lower().strip()[:50]  # Compare les 50 premiers caractères
    for ancienne in _dernieres_reponses[-5:]:
        if texte_clean in ancienne.lower() or ancienne.lower()[:50] in texte_clean:
            return True
    return False

def _ajouter_memoire(texte: str) -> None:
    """Ajoute la réponse à la mémoire anti-répétition."""
    _dernieres_reponses.append(texte)
    if len(_dernieres_reponses) > 5:
        _dernieres_reponses.pop(0)

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
    Construit le prompt avec logique de réponse directe + anti-répétition.
    """
    nom_langue = NOM_LANGUE.get(langue, "français")
    date_actuelle = get_current_date()
    hist_texte = _construire_historique(historique)
    contexte_texte = f"\n📌 CONTEXTE DU POST : « {contexte_post[:150]} »\n" if contexte_post else ""
    
    # 🚨 CONSIGNE SPÉCIALE POUR QUESTIONS DIRECTES
    if intention == "question_directe":
        consigne_speciale = """
🚨 ALERTE QUESTION DIRECTE :
L'utilisateur pose une question explicite. Tu DOIS y répondre directement et complètement.
- Ne relance PAS avec une autre question.
- Ne change PAS de sujet.
- Donne une réponse claire, utile, et honnête.
- Si c'est une question business ("pourquoi m'abonner ?"), donne 2-3 arguments concrets.
- Si tu ne sais pas, dis-le honnêtement au lieu de dévier.
"""
    else:
        consigne_speciale = """
✅ MODE CONVERSATION NORMALE :
- Alterne entre donner une info/avis et poser UNE question.
- Sois imprévisible : parfois court, parfois avec une anecdote.
- Ne parle PAS de tech sauf si l'utilisateur en parle.
"""
    
    # 🧠 MÉMOIRE ANTI-RÉPÉTITION
    memoire_texte = ""
    if _dernieres_reponses:
        memoire_texte = "\n🚫 TES 5 DERNIÈRES RÉPONSES (NE LES RÉPÈTE PAS) :\n"
        for i, rep in enumerate(_dernieres_reponses[-5:], 1):
            memoire_texte += f"{i}. {rep[:80]}...\n"
    
    prompt = f"""Tu es {BOT_NAME}, un humain normal qui discute sur Messenger. Tu n'es PAS un assistant, PAS un bot.

📅 DATE ACTUELLE : {date_actuelle}

{consigne_speciale}

{memoire_texte}

🎯 RÈGLES ABSOLUES :
1. UNE SEULE RÉPONSE : Tu envoies UN SEUL message, pas plusieurs bulles.
2. PAS DE RÉPÉTITION : Ne redis jamais ce que tu viens de dire (voir liste ci-dessus).
3. LONGUEUR VARIABLE : 1 à 3 phrases, mais pas toujours la même longueur.
4. TON NATUREL : Utilise "tu", "je", des expressions naturelles ("Ah ouais", "Moi j'trouve que").
5. PAS DE TECH FORCÉ : Ne parle pas de GPU, Redmi, pilotes NVIDIA sauf si l'utilisateur en parle.
6. PAS DE PSYCHANALYSE : Ne dis pas "t'as l'air de bloquer", "t'es dans tel état".

❌ INTERDICTIONS :
- JAMAIS de "Salut/Bonjour/Yo" sauf si c'est le TOUT PREMIER message.
- JAMAIS de listes, markdown, gras.
- JAMAIS plus d'1 emoji tous les 5 messages.
- JAMAIS de "En tant qu'IA...", "Je suis un bot...".
- JAMAIS de "Ah tu m'as démasqué" ou aveu de script.

{contexte_texte}
{hist_texte}

📩 MESSAGE DE L'UTILISATEUR : "{message}"

🔑 CONSIGNE FINALE :
Réponds en {nom_langue} comme un humain normal.
Si c'est une question → réponds directement.
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
    """
    Génère une réponse via Mistral ou Gemini avec anti-répétition.
    """
    if historique is None:
        historique = []
    
    prompt = _prompt_reponse(message, langue, intention, contexte_post, historique)
    
    # Pause réflexion humaine
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
                            {"role": "system", "content": "Tu es un humain normal. Tu réponds directement aux questions. Tu ne répètes jamais tes dernières phrases. Tu envoies un seul message."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 150,
                        "temperature": 0.9
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["choices"][0]["message"]["content"])
                
                # 🚫 ANTI-RÉPÉTITION : si déjà dit, régénère avec fallback
                if _verifier_repetition(reponse):
                    print(f"🔁 Répétition détectée, fallback...")
                    reponse = random.choice([
                        "Ah ouais, je vois ce que tu veux dire.",
                        "Je comprends, c'est pas toujours évident.",
                        "Ouais, je suis d'accord avec toi.",
                        "C'est marrant que tu dises ça, j'y pensais justement.",
                        "Honnêtement ? Je sais pas trop. Mais ça mérite qu'on regarde.",
                    ])
                
                _ajouter_memoire(reponse)
                print(f"🧠 Mistral final: {reponse[:60]}...")
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
                
                if _verifier_repetition(reponse):
                    print(f"🔁 Répétition détectée, fallback...")
                    reponse = random.choice([
                        "Ah ouais, je vois ce que tu veux dire.",
                        "Je comprends, c'est pas toujours évident.",
                        "Ouais, je suis d'accord avec toi.",
                    ])
                
                _ajouter_memoire(reponse)
                print(f"🧠 Gemini final: {reponse[:60]}...")
                return reponse
        except Exception as e:
            print(f"⚠️  Gemini échoué : {e}")
    
    # Fallback ultime
    fallbacks = [
        "Ah ouais, je vois ce que tu veux dire.",
        "Je comprends, c'est pas toujours évident.",
        "Ouais, je suis d'accord avec toi.",
        "C'est marrant que tu dises ça, j'y pensais justement.",
    ]
    reponse = random.choice(fallbacks)
    _ajouter_memoire(reponse)
    return reponse