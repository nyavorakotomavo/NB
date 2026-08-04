"""
NB — Analyse d'intention du message.
AJOUT : Détection pro vs casual + questions business prioritaires.
"""
import re

_PATTERNS = {
    # 🚨 PRIORITÉ 1 : Questions business/pro (doivent être répondues sérieusement)
    "question_pro": [
        r"\bpourquoi.*abonner\b", r"\bpourquoi.*ici\b", r"\bavantage\b",
        r"\bdifférence\b", r"\bconcurren", r"\bmieux\b", r"\bprix\b",
        r"\btarif\b", r"\bpayer\b", r"\bgratuit\b", r"\boffre\b",
        r"\bproduit\b", r"\bservice\b", r"\blive\b", r"\bformation\b",
        r"\bpourquoi.*page\b", r"\bc'est quoi.*page\b",
        r"\?",  # Toute question avec ? est prioritaire
    ],
    
    # 🥈 PRIORITÉ 2 : Spam
    "spam": [
        r"\bbitcoin\b", r"\bcrypto\b.*\binvest", r"\bgagnez\b",
        r"\bfree money\b", r"\bclick here\b", r"\bhttps?://\S+\b",
    ],
    
    # 🥉 PRIORITÉ 3 : Intentions conversationnelles
    "remerciement": [
        r"\bmerci\b", r"\bthank", r"\bmisaotra\b", r"\bsuper\b",
    ],
    "demande_aide": [
        r"\baide\b", r"\bhelp\b", r"\bproblème\b", r"\bbug\b",
    ],
    "avis_positif": [r"\bj'adore\b", r"\blove\b", r"\bincroyable\b"],
    "avis_negatif": [r"\bnul\b", r"\bmauvais\b", r"\bterrible\b"],
    "petit_talk": [
        r"\bsalut\b", r"\bhello\b", r"\bhey\b", r"\byo\b",
        r"\bça va\b", r"\bquoi de neuf\b", r"\brien\b",
    ],
}

def analyser_intention(texte: str) -> str:
    texte_lower = texte.lower()
    scores: dict[str, int] = {}
    
    for intention, patterns in _PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, texte_lower))
        if score > 0:
            scores[intention] = score
    
    # 🚨 RÈGLE ABSOLUE : question_pro > tout le reste
    if "question_pro" in scores:
        return "question_pro"
    
    if "spam" in scores and scores["spam"] >= 1:
        return "spam"
    
    if not scores:
        return "conversation"
    
    return max(scores, key=scores.get)

def detecter_contexte_conversation(historique: list[dict]) -> str:
    """
    Détecte si la conversation est pro ou casual.
    Regarde les 5 derniers messages pour déterminer le ton.
    """
    if not historique:
        return "unknown"
    
    mots_pro = {"abonner", "prix", "tarif", "payer", "offre", "produit", "service", "live", "formation", "concurren", "avantage", "différence"}
    mots_casual = {"film", "nolan", "glace", "week-end", "salut", "yo", "ça va", "rien", "discuter"}
    
    score_pro = 0
    score_casual = 0
    
    for msg in historique[-5:]:
        contenu = msg.get("contenu", "").lower()
        score_pro += sum(1 for m in mots_pro if m in contenu)
        score_casual += sum(1 for m in mots_casual if m in contenu)
    
    if score_pro > score_casual:
        return "pro"
    elif score_casual > score_pro:
        return "casual"
    else:
        return "neutral"