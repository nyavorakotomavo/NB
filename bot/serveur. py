"""
NB — Serveur FastAPI (webhook Facebook).
Reçoit les événements Facebook et répond en temps réel.

Événements gérés :
  - Messages Messenger
  - Commentaires sur les posts
  - Réactions sur les posts
"""
import time

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from bot.config import FB_VERIFY_TOKEN, BOT_NAME
from bot.fb_client import (
    verifier_signature,
    repondre_message,
    repondre_commentaire,
    commenter_post,
    get_post_message,
)
from bot.ai_responder import generer_reponse
from bot.language_detector import detecter_langue
from bot.intent_analyzer import analyser_intention
from bot.conversation_store import (
    sauvegarder_message,
    get_historique,
    log_interaction,
)

app = FastAPI(title=f"{BOT_NAME} — Nyavo Bot")

# Cache pour éviter de répondre plusieurs fois aux réactions d'un même post
_reactions_traitees: set[str] = set()


# ──────────────────────────────────────────────
# Vérification du webhook (GET)
# ──────────────────────────────────────────────
@app.get("/webhook")
async def verify_webhook(request: Request):
    """Facebook envoie un GET pour vérifier l'URL du webhook."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == FB_VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    return Response(status_code=403)


# ──────────────────────────────────────────────
# Réception des événements (POST)
# ──────────────────────────────────────────────
@app.post("/webhook")
async def handle_webhook(request: Request):
    """Reçoit et traite les événements Facebook."""
    body = await request.body()

    # Vérifier la signature Facebook
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verifier_signature(body, signature):
        return Response(status_code=403)

    data = await request.json()

    for entry in data.get("entry", []):
        # ── Messages Messenger ──
        for messaging in entry.get("messaging", []):
            await _gerer_message(messaging)

        # ── Feed (commentaires + réactions) ──
        for change in entry.get("changes", []):
            value = change.get("value", {})
            item = value.get("item", "")

            if item == "comment":
                await _gerer_commentaire(value)
            elif item == "reaction":
                await _gerer_reaction(value)

    # Facebook attend un 200 rapide
    return {"status": "ok"}


# ──────────────────────────────────────────────
# Gestion des messages Messenger
# ──────────────────────────────────────────────
async def _gerer_message(messaging: dict) -> None:
    """Traite un message Messenger entrant."""
    sender_id = messaging.get("sender", {}).get("id", "")
    message_data = messaging.get("message", {})
    texte = message_data.get("text", "")

    if not sender_id or not texte:
        return

    t0 = time.time()

    # Analyse
    langue = detecter_langue(texte)
    intention = analyser_intention(texte)

    # Ignorer le spam
    if intention == "spam":
        return

    # Historique
    historique = get_historique(sender_id, "messenger")

    # Sauvegarder le message entrant
    sauvegarder_message(sender_id, "messenger", "user", texte, langue)

    # Générer la réponse
    reponse = await generer_reponse(
        message=texte,
        langue=langue,
        intention=intention,
        historique=historique,
    )

    # Envoyer
    await repondre_message(sender_id, reponse)

    # Sauvegarder la réponse
    sauvegarder_message(sender_id, "messenger", "bot", reponse, langue)

    # Analytics
    temps = time.time() - t0
    log_interaction(sender_id, "message", langue, intention, temps)

    print(f"  💬 Messenger [{langue}/{intention}] → {reponse[:60]}... ({temps:.1f}s)")


# ──────────────────────────────────────────────
# Gestion des commentaires
# ──────────────────────────────────────────────
async def _gerer_commentaire(value: dict) -> None:
    """Traite un nouveau commentaire sur un post."""
    verb = value.get("verb", "")
    if verb != "add":
        return

    comment_id = value.get("comment_id", "")
    sender_id = value.get("from", {}).get("id", "")
    texte = value.get("message", "")
    post_id = value.get("post_id", "")

    if not comment_id or not texte:
        return

    t0 = time.time()

    # Analyse
    langue = detecter_langue(texte)
    intention = analyser_intention(texte)

    # Ignorer le spam
    if intention == "spam":
        return

    # Contexte du post
    contexte = await get_post_message(post_id) if post_id else ""

    # Historique
    historique = get_historique(sender_id, "comment")

    # Sauvegarder
    sauvegarder_message(sender_id, "comment", "user", texte, langue, post_id)

    # Générer la réponse
    reponse = await generer_reponse(
        message=texte,
        langue=langue,
        intention=intention,
        contexte_post=contexte,
        historique=historique,
    )

    # Envoyer
    await repondre_commentaire(comment_id, reponse)

    # Sauvegarder
    sauvegarder_message(sender_id, "comment", "bot", reponse, langue, post_id)

    # Analytics
    temps = time.time() - t0
    log_interaction(sender_id, "commentaire", langue, intention, temps, post_id)

    print(f"  🗨️  Commentaire [{langue}/{intention}] → {reponse[:60]}... ({temps:.1f}s)")


# ──────────────────────────────────────────────
# Gestion des réactions
# ──────────────────────────────────────────────
async def _gerer_reaction(value: dict) -> None:
    """
    Traite une réaction sur un post.
    Poste un remerciement général (une seule fois par post).
    """
    verb = value.get("verb", "")
    if verb != "add":
        return

    post_id = value.get("post_id", "")
    reaction_type = value.get("reaction_type", "like")

    if not post_id:
        return

    # Un seul remerciement par post
    if post_id in _reactions_traitees:
        return
    _reactions_traitees.add(post_id)

    # Message de remerciement selon la réaction
    remerciements = {
        "like": "Merci pour le soutien ! Ça fait plaisir de voir que le contenu tech vous parle 🙏",
        "love": "Wow, merci pour tout cet amour ! Vous êtes la meilleure communauté tech 🤖❤️",
        "haha": "Content que ça vous fasse rire ! Le code c'est aussi de l'humour 😄⚡",
        "wow": "Merci ! La tech n'a pas fini de nous surprendre 🤯🔬",
        "sad": "Merci pour votre soutien 💙 On traverse ça ensemble.",
        "angry": "Merci pour votre retour. On s'améliore chaque jour 🙏",
        "care": "Merci pour votre bienveillance ! La communauté Nyavo est forte 🤝💚",
    }
    texte = remerciements.get(
        reaction_type,
        "Merci pour votre réaction ! Restez connectés pour plus de contenu tech 🚀",
    )

    try:
        await commenter_post(post_id, texte)
        log_interaction("", "reaction", "fr", "remerciement", 0.0, post_id)
        print(f"  👍 Réaction [{reaction_type}] sur {post_id} → remerciement posté")
    except Exception as e:
        print(f"  ⚠️  Erreur remerciement réaction : {e}")


# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────
@app.get("/")
async def health():
    return {"status": "ok", "bot": BOT_NAME, "version": "1.0"}


# ──────────────────────────────────────────────
# Démarrage
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)