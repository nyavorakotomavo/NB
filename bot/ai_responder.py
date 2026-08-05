"""
NB — Génération de réponses IA.
CORRECTIONS :
- Plus de "Je vérifie..." (réponse directe ou admission honnête)
- Ton cohérent (Pro = Vouvoiement strict, Casual = Tutoiement strict)
- Lecture des vrais posts (si dispo)
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
    hist_texte = "\n📜 HISTORIQUE :\n"
    for msg in historique[-MAX_HISTORY_TURNS * 2:]:
        role = "Utilisateur" if msg.get('role') == 'user' else BOT_NAME
        contenu = msg.get('contenu', '')
        hist_texte += f"- {role} : {contenu}\n"
    return hist_texte

def _detecter_intention_rapide(message: str) -> str:
    msg_lower = message.lower()
    mots_pro = ["abonner", "prix", "tarif", "payer", "offre", "produit", "service", "live", "formation", "concurren", "avantage", "différence", "contenu", "publiez", "page", "quoi", "quel", "comment", "pourquoi", "b2b", "business"]
    mots_stop = ["au revoir", "à plus", "ciao", "bye", "non", "je sais pas", "ok", "d'accord", "merci"]

    if any(m in msg_lower for m in mots_stop):
        return "stop"
    if any(m in msg_lower for m in mots_pro) or "?" in message:
        return "pro"
    return "casual"

async def _get_resume_posts() -> str:
    try:
        posts = await get_derniers_posts_page()
        if not posts:
            return "📋 Aucun post récent trouvé (ou erreur API)."
        
        resume = "📋 DERNIERS POSTS RÉELS :\n"
        for i, p in enumerate(posts[:3], 1):
            msg = (p.get("message") or "")[:80]
            resume += f"{i}. {msg}\n"
        return resume
    except Exception:
        return "📋 Impossible de lire les posts."

def _prompt_reponse(
    message: str,
    langue: str,
    intention: str,
    contexte_post: str,
    historique: list[dict],
    resume_posts: str
) -> str:
    nom_langue = NOM_LANGUE.get(langue, "français")
    date_actuelle = get_current_date()
    hist_texte = _construire_historique(historique)
    contexte_texte = f"\n📌 CONTEXTE : « {contexte_post[:150]} »\n" if contexte_post else ""

    type_ton = _detecter_intention_rapide(message)

    if type_ton == "stop":
        consigne_ton = """
🛑 SIGNAL D'ARRÊT :
- Réponds TRÈS COURT (1 phrase max).
- NE POSE PAS DE QUESTION.
- Exemple : "À plus !", "Ok.", "Pas de souci."
"""
    elif type_ton == "pro":
        consigne_ton = f"""
🚨 MODE PROFESSIONNEL (QUESTION) :
- UTILISE LE VOUVOIEMENT ("vous", "votre") OBLIGATOIRE.
- TON FORMEL, SÉRIEUX.
- BASE-TOI SUR LES POSTS CI-DESSOUS SI POSSIBLE.
- SI TU NE SAIS PAS : Dis simplement "Je n'ai pas cette information pour le moment" ou donne une définition générale si c'est une question de connaissance (ex: B2B).
- NE DIS JAMAIS "Je vérifie", "Je consulte", "Un instant". Réponds tout de suite.

{resume_posts}
"""
    else:
        consigne_ton = """
✅ MODE CONVERSATION (CASUAL) :
- UTILISE LE TUTOIEMENT ("tu", "ton").
- Ton décontracté, pote geek.
- Court, direct.
"""

    memoire_texte = ""
    if _dernieres_reponses:
        memoire_texte = "\n🚫 TES 5 DERNIÈRES RÉPONSES (NE LES RÉPÈTE PAS) :\n"
        for i, rep in enumerate(_dernieres_reponses[-5:], 1):
            memoire_texte += f"{i}. {rep[:80]}...\n"

    prompt = f"""Tu es {BOT_NAME}, community manager de Nyavodroid.

📅 DATE : {date_actuelle}

{consigne_ton}

{memoire_texte}

🎯 RÈGLES :
1. UNE SEULE RÉPONSE.
2. PAS DE RÉPÉTITION.
3. VÉRITÉ : Ne mens pas.
4. PAS DE "JE VÉRIFIE" : Réponds directement avec ce que tu sais.
5. LONGUEUR : 1 à 3 phrases max.

{contexte_texte}
{hist_texte}

📩 MESSAGE : "{message}"

🔑 CONSIGNE :
Réponds en {nom_langue}.
Adapte le ton (Pro/Casual).
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

    resume_posts = await _get_resume_posts()
    prompt = _prompt_reponse(message, langue, intention, contexte_post, historique, resume_posts)

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
                            {"role": "system", "content": "Tu es un community manager pro. Tu réponds directement. Tu ne dis jamais 'je vérifie'. Tu utilises le vouvoiement pour les questions pro."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 150,
                        "temperature": 0.7
                    }
                )
                resp.raise_for_status()
                reponse = _nettoyer(resp.json()["choices"][0]["message"]["content"])

                if _verifier_repetition(reponse):
                    reponse = "Je n'ai pas d'autres informations à ce sujet pour le moment."

                _ajouter_memoire(reponse)
                return reponse
        except Exception as e:
            print(f"⚠️ Mistral échoué : {e}")

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
                    reponse = "Je n'ai pas d'autres informations à ce sujet pour le moment."

                _ajouter_memoire(reponse)
                return reponse
        except Exception as e:
            print(f"⚠️ Gemini échoué : {e}")

    # Fallback ULTIME (Direct, pas de "je vérifie")
    fallbacks = [
        "Je n'ai pas cette information précise pour le moment.",
        "C'est une excellente question, mais je n'ai pas la réponse exacte sous la main.",
        "Nous publions surtout des contenus tech et dev. Avez-vous une autre question ?",
    ]
    reponse = random.choice(fallbacks)
    _ajouter_memoire(reponse)
    return reponse