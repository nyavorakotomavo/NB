"""
NB — Détection de langue (FR / EN / MG).
"""
import re

# Mots-clés par langue (haute confiance)
_MOTS_MG = {
    "salama", "misaotra", "inona", "ahoana", "ve", "dia", "no", "ny",
    "azy", "izany", "tsy", "efa", "mbola", "koa", "aza", "aty",
    "manao", "mila", "tiany", "mahay", "tena", "be", "kely",
}
_MOTS_FR = {
    "bonjour", "merci", "est-ce", "comment", "pourquoi", "salut",
    "oui", "non", "avec", "dans", "pour", "une", "des", "les",
    "c'est", "qu'est", "j'ai", "je", "tu", "nous", "vous",
}
_MOTS_EN = {
    "hello", "thank", "what", "how", "why", "the", "and", "is",
    "are", "can", "you", "i", "we", "this", "that", "please",
}


def detecter_langue(texte: str) -> str:
    """
    Retourne 'fr', 'en' ou 'mg'.
    Stratégie : comptage de mots-clés + heuristiques.
    """
    texte_lower = texte.lower()
    mots = set(re.findall(r'\b\w+\b', texte_lower))

    score_mg = len(mots & _MOTS_MG)
    score_fr = len(mots & _MOTS_FR)
    score_en = len(mots & _MOTS_EN)

    # Le malagasy a des mots très distinctifs
    if score_mg >= 2 or (score_mg > score_fr and score_mg > score_en):
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