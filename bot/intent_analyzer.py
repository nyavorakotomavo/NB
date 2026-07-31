"""
NB — Analyse d'intention du message.
"""
import re

# Patterns par intention
_PATTERNS = {
    "remerciement": [
        r"\bmerci\b", r"\bthank", r"\bmisaotra\b", r"\bsuper\b",
        r"\bgénial\b", r"\btop\b", r"\bbravo\b", r"\bgreat\b",
        r"\bawesome\b", r"\bnice\b", r"\btsara\b", r"\baraka\b",
    ],
    "question_technique": [
        r"\bcomment\b", r"\bpourquoi\b", r"\bwhat\b", r"\bhow\b",
        r"\bwhy\b", r"\binona\b", r"\bahoana\b", r"\best-ce\b",
        r"\bqu'est\b", r"\bcan you\b", r"\bexpliqu", r"\bexplain\b",
        r"\bmanazava\b", r"\bcode\b", r"\bapi\b", r"\bdns\b",
        r"\bpython\b", r"\bserveur\b", r"\balgorithme\b",
    ],
    "demande_aide": [
        r"\baide\b", r"\bhelp\b", r"\bampio\b", r"\bproblème\b",
        r"\bbug\b", r"\berreur\b", r"\berror\b", r"\bdiso\b",
        r"\bje n'arrive\b", r"\bi can't\b", r"\btsy afaka\b",
    ],
    "avis_positif": [
        r"\bj'adore\b", r"\blove\b", r"\btiako\b", r"\bincroyable\b",
        r"\bamazing\b", r"\bfantastique\b", r"\btrop bien\b",
    ],
    "avis_negatif": [
        r"\bnul\b", r"\bmauvais\b", r"\bbad\b", r"\bterrible\b",
        r"\bhorrible\b", r"\bratsy\b", r"\bdaube\b",
    ],
    "spam": [
        r"\bbitcoin\b", r"\bcrypto\b.*\binvest", r"\bgagnez\b",
        r"\bfree money\b", r"\bclick here\b", r"\bhttps?://\S+\b",
        r"\bpromo\b", r"\bréduction\b.*\bcode\b",
    ],
}


def analyser_intention(texte: str) -> str:
    """
    Retourne l'intention détectée :
    remerciement, question_technique, demande_aide,
    avis_positif, avis_negatif, spam, conversation
    """
    texte_lower = texte.lower()

    scores: dict[str, int] = {}
    for intention, patterns in _PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, texte_lower))
        if score > 0:
            scores[intention] = score

    if not scores:
        return "conversation"

    meilleure = max(scores, key=scores.get)  # type: ignore[arg-type]

    # Le spam est prioritaire
    if "spam" in scores and scores["spam"] >= 2:
        return "spam"

    return meilleure