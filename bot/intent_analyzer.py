"""
NB — Analyse d'intention du message.
CORRECTIONS :
- Détection des signaux d'arrêt (au revoir, non, je sais pas)
- Priorité absolue aux questions pro
- Limitation stricte des questions conversationnelles
"""
import re

_PATTERNS = {
    #  PRIORITÉ 0 : Signaux d'arrêt (le bot doit s'arrêter ou être très court)
    "signal_arret": [
        r"\bau revoir\b", r"\bà plus\b", r"\bciao\b", r"\bsalut\b.*\bfin\b",
        r"\bbonne nuit\b", r"\bbonne soirée\b", r"\bje dois y aller\b",
        r"\bje te laisse\b", r"\bà bientôt\b", r"\bbye\b",
    ],
    
    # 🚫 PRIORITÉ 1 : Réponses courtes/négatives (ne pas relancer avec une question)
    "reponse_courte": [
        r"\bnon\b", r"\boui\b", r"\bje sais pas\b", r"\bjsp\b", r"\bbof\b",
        r"\bpas vraiment\b", r"\bpeut-être\b", r"\bmouais\b", r"\bok\b",
        r"\bd'accord\b", r"\bvaleurs\b", r"\bon verra\b",
    ],
    
    # 🚨 PRIORITÉ 2 : Questions business/pro (réponse sérieuse obligatoire)
    "question_pro": [
        r"\bpourquoi.*abonner\b", r"\bpourquoi.*ici\b", r"\bavantage\b",
        r"\bdifférence\b", r"\bconcurren", r"\bmieux\b", r"\bprix\b",
        r"\btarif\b", r"\bpayer\b", r"\bgratuit\b", r"\boffre\b",
        r"\bproduit\b", r"\bservice\b", r"\blive\b", r"\bformation\b",
        r"\?",
    ],
    
    # 🥈 PRIORITÉ 3 : Spam
    "spam": [
        r"\bbitcoin\b", r"\bcrypto\b.*\binvest", r"\bgagnez\b",
        r"\bfree money\b", r"\bclick here\b", r"\bhttps?://\S+\b",
    ],
    
    # 🥉 PRIORITÉ 4 : Intentions conversationnelles
    "remerciement": [r"\bmerci\b", r"\bthank", r"\bmisaotra\b", r"\bsuper\b"],
    "demande_aide": [r"\baide\b", r"\bhelp\b", r"\bproblème\b", r"\bbug\b"],
    "avis_positif": [r"\bj'adore\b", r"\blove\b", r"\bincroyable\b"],
    "avis_negatif": [r"\bnul\b", r"\bmauvais\b", r"\bterrible\b"],
    "petit_talk": [r"\bsalut\b", r"\bhello\b", r"\bhey\b", r"\byo\b", r"\bça va\b"],
}

def analyser_intention(texte: str) -> str:
    texte_lower = texte.lower()
    scores: dict[str, int] = {}
    
    for intention, patterns in _PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, texte_lower))
        if score > 0:
            scores[intention] = score
    
    #  RÈGLE ABSOLUE : signal_arret > tout le reste
    if "signal_arret" in scores:
        return "signal_arret"
    
    # 🚫 Réponse courte → ne pas relancer avec une question
    if "reponse_courte" in scores:
        return "reponse_courte"
    
    # 🚨 Question pro → réponse sérieuse
    if "question_pro" in scores:
        return "question_pro"
    
    if "spam" in scores and scores["spam"] >= 1:
        return "spam"
    
    if not scores:
        return "conversation"
    
    return max(scores, key=scores.get)

def detecter_contexte_conversation(historique: list[dict]) -> str:
    """Détecte si la conversation est pro ou casual."""
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