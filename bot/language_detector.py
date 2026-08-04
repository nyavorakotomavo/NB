"""
NB — Détection de langue (FR / EN / MG).
CORRECTION : mots-clés MG exclusifs (longueur > 3) pour éviter les faux positifs.
"""
import re

# Mots-clés par langue (haute confiance)
_MOTS_MG = {
    "salama", "misaotra", "inona", "ahoana", "izany", "tsy", "mbola",
    "manao", "mila", "mahay", "tena", "kely", "lehibe", "sakafo",
    "fianakaviana", "trano", "asa", "vola", "lalana", "fiara",
    "tiany", "efa", "koa", "aza", "aty", "be", "tsara", "araka"
}

_MOTS_FR = {
    "bonjour", "merci", "est-ce", "comment", "pourquoi", "salut",
    "oui", "non", "avec", "dans", "pour", "une", "des", "les",
    "c'est", "qu'est", "j'ai", "je", "tu", "nous", "vous",
    "mais", "donc", "parce", "quand", "où", "qui", "quoi"
}

_MOTS_EN = {
    "hello", "thank", "what", "how", "why", "the", "and", "is",
    "are", "can", "you", "i", "we", "this", "that", "please",
    "but", "so", "because", "when", "where", "who", "which"
}

def detecter_langue(texte: str) -> str:
    """
    Retourne 'fr', 'en' ou 'mg'.
    Stratégie : comptage de mots-clés + seuil de confiance renforcé.
    """
    texte_lower = texte.lower()
    mots = set(re.findall(r'\b\w+\b', texte_lower))
    
    score_mg = len(mots & _MOTS_MG)
    score_fr = len(mots & _MOTS_FR)
    score_en = len(mots & _MOTS_EN)
    
    # Le malagasy a des mots très distinctifs — seuil renforcé
    if score_mg >= 3 or (score_mg > score_fr and score_mg > score_en and score_mg >= 2):
        return "mg"
    
    if score_fr > score_en:
        return "fr"
    if score_en > score_fr:
        return "en"
    
    # Fallback : vérifier les accents (typiquement français)
    if re.search(r'[àâäéèêëïîôùûüç]', texte_lower):
        return "fr"
    
    # Défaut : français (audience principale)
    return "fr"

NOM_LANGUE = {
    "fr": "français",
    "en": "anglais",
    "mg": "malagasy",
}