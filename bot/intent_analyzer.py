"""
NB — Analyse d'intention du message.
CORRECTION : Priorité absolue aux questions directes (business/support).
"""
import re

_PATTERNS = {
    #  PRIORITÉ 1 : Questions directes (doivent être répondues immédiatement)
    "question_directe": [
        r"\bpourquoi\b", r"\bcomment\b", r"\bquand\b", r"\boù\b", r"\bqui\b",
        r"\bquel\b", r"\best-ce\b", r"\bqu'est\b", r"\bc'est quoi\b",
        r"\btu entends\b", r"\btu veux dire\b", r"\bexplique\b",
        r"\bpourquoi.*abonner\b", r"\bpourquoi.*ici\b", r"\bavantage\b",
        r"\bdifférence\b", r"\bconcurren", r"\bmieux\b",
        r"\?",  # Tout message avec un point d'interrogation est une question directe
    ],
    
    # 🥈 PRIORITÉ 2 : Spam (à bloquer)
    "spam": [
        r"\bbitcoin\b", r"\bcrypto\b.*\binvest", r"\bgagnez\b",
        r"\bfree money\b", r"\bclick here\b", r"\bhttps?://\S+\b",
        r"\bpromo\b", r"\bréduction\b.*\bcode\b",
    ],
    
    # 🥉 PRIORITÉ 3 : Intentions conversationnelles
    "remerciement": [
        r"\bmerci\b", r"\bthank", r"\bmisaotra\b", r"\bsuper\b",
        r"\bgénial\b", r"\btop\b", r"\bbravo\b",
    ],
    "demande_aide": [
        r"\baide\b", r"\bhelp\b", r"\bampio\b", r"\bproblème\b",
        r"\bbug\b", r"\berreur\b", r"\berror\b",
    ],
    "avis_positif": [
        r"\bj'adore\b", r"\blove\b", r"\btiako\b", r"\bincroyable\b",
    ],
    "avis_negatif": [
        r"\bnul\b", r"\bmauvais\b", r"\bbad\b", r"\bterrible\b",
    ],
    "petit_talk": [
        r"\bsalut\b", r"\bhello\b", r"\bhey\b", r"\byo\b",
        r"\bça va\b", r"\bquoi de neuf\b", r"\brien\b",
    ],
}

def analyser_intention(texte: str) -> str:
    """
    Retourne l'intention avec priorité : question_directe > spam > autres.
    """
    texte_lower = texte.lower()
    scores: dict[str, int] = {}
    
    for intention, patterns in _PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, texte_lower))
        if score > 0:
            scores[intention] = score
    
    # 🚨 RÈGLE ABSOLUE : Si question_directe détectée → c'est l'intention finale
    if "question_directe" in scores:
        return "question_directe"
    
    # 🚫 Spam prioritaire sur le reste
    if "spam" in scores and scores["spam"] >= 1:
        return "spam"
    
    if not scores:
        return "conversation"
    
    return max(scores, key=scores.get)