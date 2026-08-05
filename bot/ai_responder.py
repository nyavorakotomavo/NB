"""
NB — Génération de réponses IA (Mistral → Gemini).
CORRECTIONS MAJEURES :
- Lecture des VRAIS posts publiés (source de vérité Facebook)
- Ton FORMEL pour les questions pro / CASUAL pour la conversation
- Anti-répétition stricte + Respect des signaux d'arrêt
- Plus d'invention de contenu
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
from bot.fb_client import get_derniers_posts_page

# Mémoire anti-répétition locale (5 derniers messages)
_dernieres_reponses: list[str] = []

def _nettoyer(texte: str) -> str:
    """Nettoie le texte des caractères invisibles et du formatage."""
    texte = re.sub(r'[\u200e\u200f\u200b\u200c\u200d\ufeff\u00ad\u2060\u180e\u202a-\u202e\u2066-\u2069]', '', texte)
    texte = re.sub(r'\*\*(.*?)\*\*', r'\1', texte)
    texte = re.sub(r'\*(.*?)\*', r'\1', texte)
    texte = re.sub(r'^[-•]\s*', '', texte, flags=re.MULTILINE)
    return texte.strip()

def _verifier_repetition(texte: str) -> bool:
    """Vérifie si le texte ressemble trop aux dernières réponses."""
    texte_clean = texte.lower().strip()[:50]
    for ancienne in _dernieres_reponses[-5:]:
        if texte_clean in ancienne.lower() or ancienne.lower()[:50] in texte_clean:
            return True
    return False

def _ajouter_memoire(texte: str) -> None:
    """Ajoute la réponse à la mémoire locale."""
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

def _detecter_intention_rapide(message: str) -> str:
    """Détection rapide pour choisir le ton (Pro vs Casual)."""
    msg_lower = message.lower()
    mots_pro = ["abonner", "prix", "tarif", "payer", "offre", "produit", "service", "live", "formation", "concurren", "avantage", "différence", "contenu", "publiez", "page", "quoi", "quel", "comment", "pourquoi"]
    mots_stop = ["au revoir", "à plus", "ciao", "bye", "non", "je sais pas", "ok", "d'accord", "merci"]

    if any(m in msg_lower for m in mots_stop):
        return "stop"
    if any(m in msg_lower for m in mots_pro) or "?" in message:
        return "pro"
    return "casual"

async def _get_resume_posts() -> str:
    """Récupère les vrais posts pour injecter dans le prompt."""
    try:
        posts = await get_derniers_posts_page()
        if not posts:
            return "📋 Aucun post récent trouvé."

        resume = "📋 DERNIERS POSTS RÉELS PUBLIÉS (SOURCE DE VÉRITÉ) :\n"
        for i, p in enumerate(posts[:5], 1):
            msg = (p.get("message") or "Pas de texte")[:100]
            resume += f"{i}. {msg}\n"
        return resume
    except Exception:
        return "📋 Impossible de récupérer les posts actuellement."

def _prompt_reponse(
    message: str,
    langue: str,
    intention: str,
    contexte_post: str,
    historique: list[dict],
    resume_posts: str
) -> str:
    """Construit le prompt dynamique selon le contexte."""
    nom_langue = NOM_LANGUE.get(langue, "français")
    date_actuelle = get_current_date()
    hist_texte = _construire_historique(historique)
    contexte_texte = f"\n📌 CONTEXTE DU POST : « {contexte_post[:150]} »\n" if contexte_post else ""

    type_ton = _detecter_intention_rapide(message)

    # --- LOGIQUE DE TON ---
    if type_ton == "stop":
        consigne_ton = """
🛑 SIGNAL D'ARRÊT / RÉPONSE COURTE :
L'utilisateur veut finir ou répond brièvement.
- Réponds TRÈS COURT (1 phrase max).
- NE POSE PAS DE QUESTION.
- Exemple : "À plus !", "Ok, je vois.", "Pas de souci."
"""
    elif type_ton == "pro":
        consigne_ton = f"""
🚨 MODE PROFESSIONNEL (QUESTION SUR LA PAGE) :
L'utilisateur demande des infos sur la page, le contenu, ou pourquoi s'abonner.
- UTILISE LE VOUVOIEMENT ("vous", "votre").
- TON FORMEL, SÉRIEUX, RESPECTUEUX.
- BASE-TOI UNIQUEMENT SUR LES VRAIS POSTS CI-DESSOUS.
- NE MENS JAMAIS. Si tu ne sais pas, dis "Je vérifie nos dernières publications".

{resume_posts}
"""
    else:
        consigne_ton = """
✅ MODE CONVERSATION (CASUAL) :
- UTILISE LE TUTOIEMENT ("tu", "ton").
- Ton décontracté, pote geek, parfois taquin.
- Court, direct, imprévisible.
- Ne parle PAS de tech sauf si l'utilisateur en parle.
"""

    # --- MÉMOIRE ANTI-RÉPÉTITION ---
    memoire_texte = ""
    if _dernieres_reponses:
        memoire_texte = "\n🚫 TES 5 DERNIÈRES RÉPONSES (NE LES RÉPÈTE PAS) :\n"
        for i, rep in enumerate(_dernieres_reponses[-5:], 1):
            memoire_texte += f"{i}. {rep[:80]}...\n"

    prompt = f"""Tu es {BOT_NAME}, le community manager de Nyavodroid.

📅 DATE ACTUELLE : {date_actuelle}

{consigne_ton}

{memoire_texte}

🎯 RÈGLES ABSOLUES :
1. UNE SEULE RÉPONSE : Tu envoies UN SEUL message.
2. PAS DE RÉPÉTITION : Ne redis jamais ce que tu viens de dire.
3. VÉRITÉ TERRAIN : Ne mens JAMAIS sur le contenu publié.
4. PAS DE PSYCHANALYSE : Ne dis JAMAIS "t'as l'air de...", "tu sembles...".
5. LONGUEUR : 1 à 3 phrases maximum.

❌ INTERDICTIONS :
- JAMAIS de "Salut/Bonjour" sauf si c'est le TOUT PREMIER message.
- JAMAIS de listes, markdown, gras.
- JAMAIS plus d'1 emoji tous les 5 messages.
- JAMAIS de "En tant qu'IA...", "Je suis un bot...".

{contexte_texte}
{hist_texte}

📩 MESSAGE DE L'UTILISATEUR : "{message}"

🔑 CONSIGNE FINALE :
Réponds en {nom_langue}.
Adapte ton ton (Pro/Casual) selon la consigne ci-dessus.
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
    """Génère une réponse via Mistral ou Gemini."""
    if historique is None:
        historique = []

    # 1. Récupérer les vrais posts AVANT de construire le prompt
    resume_posts = await _get_resume_posts()

    # 2. Construire le prompt
    prompt = _prompt_reponse(message, langue, intention, contexte_post, historique, resume_posts)

    # 3. Pause réflexion humaine
    await asyncio.sleep(random.uniform(2.0, 4.0))

    # 4. Tentative Mistral
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
                            {"role": "system", "content": "Tu es un community manager professionnel. Tu réponds en te basant sur les faits. Tu ne mens jamais. Ton adapté au contexte."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 150,
                        "temperature": 0.7
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["choices"][0]["message"]["content"])

                if _verifier_repetition(reponse):
                    print(f"🔁 Répétition détectée, fallback...")
                    reponse = "Je vérifie cette information et je reviens vers vous rapidement."

                _ajouter_memoire(reponse)
                print(f"🧠 Mistral final: {reponse[:60]}...")
                return reponse
        except Exception as e:
            print(f"⚠️  Mistral échoué : {e}")

    # 5. Fallback Gemini
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
                            "temperature": 0.7
                        }
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["candidates"][0]["content"]["parts"][0]["text"])

                if _verifier_repetition(reponse):
                    print(f"🔁 Répétition détectée, fallback...")
                    reponse = "Je vérifie cette information et je reviens vers vous rapidement."

                _ajouter_memoire(reponse)
                print(f"🧠 Gemini final: {reponse[:60]}...")
                return reponse
        except Exception as e:
            print(f"⚠️  Gemini échoué : {e}")

    # 6. Fallback ultime
    fallbacks = [
        "Je vérifie cette information et je reviens vers vous rapidement.",
        "Merci pour votre question. Je consulte nos dernières publications.",
        "Un instant, je regarde ce qui a été publié récemment.",
    ]
    reponse = random.choice(fallbacks)
    _ajouter_memoire(reponse)
    return reponse