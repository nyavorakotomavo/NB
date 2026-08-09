"""
NB — Serveur FastAPI.
Gère :
- webhook Facebook Messenger
- commentaires
- réactions
- alertes SEON via /alert
"""

import time
import os
import secrets

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from bot.config import (
    FB_VERIFY_TOKEN,
    BOT_NAME,
    FB_PAGE_ID,
    OWNER_PSID,
    SEON_ALERT_TOKEN,
)

from bot.fb_client import (
    verifier_signature,
    envoyer_message_humain,
    commenter_post,
    get_post_message,
    repondre_message,
)

from bot.ai_responder import generer_reponse
from bot.language_detector import detecter_langue
from bot.intent_analyzer import analyser_intention
from bot.conversation_store import (
    sauvegarder_message,
    get_historique,
    log_interaction,
)


print("=" * 50)
print(f"🤖 {BOT_NAME} - Démarrage du serveur...")
print(f"📱 FB_PAGE_ID: {FB_PAGE_ID[:10] if FB_PAGE_ID else 'NON DÉFINI'}...")
print(f"🔑 FB_VERIFY_TOKEN: {FB_VERIFY_TOKEN[:10] if FB_VERIFY_TOKEN else 'NON DÉFINI'}...")
print(f"👤 OWNER_PSID: {'PRÉSENT' if OWNER_PSID else 'NON DÉFINI'}")
print(f"🚨 SEON_ALERT_TOKEN: {'PRÉSENT' if SEON_ALERT_TOKEN else 'NON DÉFINI'}")
print(f"🌐 Port: {int(os.environ.get('PORT', 8080))}")
print("=" * 50)


app = FastAPI(title=f"{BOT_NAME} — Nyavodroid Bot")


# ─── Anti-rafale / anti-doublon ─────────────────────────────
_messages_traites: set[str] = set()
_MAX_CACHE_SIZE = 1000
_reactions_traitees: set[str] = set()


# ─── Rate limit pour /alert ─────────────────────────────────
_alert_timestamps: list[float] = []
_MAX_ALERTS_PER_MINUTE = 10


# ─── Modèle payload SEON ────────────────────────────────────
class AlertPayload(BaseModel):
    message: str


# ─── Vérification webhook Facebook ──────────────────────────
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    print(f"🔍 GET /webhook - mode: {mode}, challenge: {challenge}")

    if mode == "subscribe" and token == FB_VERIFY_TOKEN:
        print("✅ Webhook vérifié avec succès !")
        return PlainTextResponse(challenge)

    print("❌ Échec de vérification du webhook")
    return Response(status_code=403)


# ─── Réception webhook Facebook ─────────────────────────────
@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.body()

    print("📨 REQUÊTE POST REÇUE")

    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verifier_signature(body, signature):
        print("❌ Signature invalide")
        return Response(status_code=403)

    print("✅ Signature valide")

    data = await request.json()

    for entry in data.get("entry", []):
        # --- Messages Messenger ---
        for messaging in entry.get("messaging", []):
            message_obj = messaging.get("message") or {}
            msg_id = message_obj.get("mid", "")

            if not msg_id:
                continue

            if msg_id in _messages_traites:
                print(f"⏭️ Message {msg_id} déjà traité, ignoré.")
                continue

            _messages_traites.add(msg_id)

            if len(_messages_traites) > _MAX_CACHE_SIZE:
                _messages_traites.clear()
                print("🧹 Cache anti-doublon vidé")

            print("💬 Message Messenger reçu")
            await _gerer_message(messaging)

        # --- Feed : commentaires + réactions ---
        for change in entry.get("changes", []):
            value = change.get("value", {})
            item = value.get("item", "")

            if item == "comment":
                comment_id = value.get("comment_id", "")

                if not comment_id:
                    continue

                if comment_id in _messages_traites:
                    print(f"⏭️ Commentaire {comment_id} déjà traité, ignoré.")
                    continue

                _messages_traites.add(comment_id)
                await _gerer_commentaire(value)

            elif item == "reaction":
                await _gerer_reaction(value)

    return {"status": "ok"}


# ─── Gestion message Messenger ──────────────────────────────
async def _gerer_message(messaging: dict) -> None:
    sender_id = messaging.get("sender", {}).get("id", "")
    message_data = messaging.get("message", {})
    texte = message_data.get("text", "")

    if not sender_id or not texte:
        return

    print(f"📩 Message de {sender_id}: {texte[:50]}...")

    t0 = time.time()

    langue = detecter_langue(texte)
    intention = analyser_intention(texte)

    if intention == "spam":
        print(f"🚫 Spam ignoré de {sender_id}")
        return

    historique = get_historique(sender_id, "messenger")

    sauvegarder_message(
        user_id=sender_id,
        platform="messenger",
        role="user",
        contenu=texte,
        langue=langue,
    )

    reponse = await generer_reponse(
        message=texte,
        langue=langue,
        intention=intention,
        historique=historique,
    )

    await envoyer_message_humain(
        sender_id=sender_id,
        texte=reponse,
        type_envoi="message",
    )

    sauvegarder_message(
        user_id=sender_id,
        platform="messenger",
        role="bot",
        contenu=reponse,
        langue=langue,
    )

    temps = time.time() - t0

    log_interaction(
        user_id=sender_id,
        type_interaction="message",
        langue=langue,
        intention=intention,
        temps_reponse=temps,
    )

    print(f"💬 Messenger [{langue}/{intention}] → {reponse[:60]}... ({temps:.1f}s)")


# ─── Gestion commentaire ────────────────────────────────────
async def _gerer_commentaire(value: dict) -> None:
    verb = value.get("verb", "")

    if verb != "add":
        return

    comment_id = value.get("comment_id", "")
    sender_id = value.get("from", {}).get("id", "") or "anonymous"
    texte = value.get("message", "")
    post_id = value.get("post_id", "")

    if not comment_id or not texte:
        return

    print(f"🗨️ Commentaire de {sender_id}: {texte[:50]}...")

    t0 = time.time()

    langue = detecter_langue(texte)
    intention = analyser_intention(texte)

    if intention == "spam":
        print(f"🚫 Spam ignoré de {sender_id}")
        return

    contexte = await get_post_message(post_id) if post_id else ""
    historique = get_historique(sender_id, "comment")

    sauvegarder_message(
        user_id=sender_id,
        platform="comment",
        role="user",
        contenu=texte,
        langue=langue,
        post_id=post_id,
    )

    reponse = await generer_reponse(
        message=texte,
        langue=langue,
        intention=intention,
        contexte_post=contexte,
        historique=historique,
    )

    await envoyer_message_humain(
        sender_id=comment_id,
        texte=reponse,
        type_envoi="commentaire",
    )

    sauvegarder_message(
        user_id=sender_id,
        platform="comment",
        role="bot",
        contenu=reponse,
        langue=langue,
        post_id=post_id,
    )

    temps = time.time() - t0

    log_interaction(
        user_id=sender_id,
        type_interaction="commentaire",
        langue=langue,
        intention=intention,
        temps_reponse=temps,
        post_id=post_id,
    )

    print(f"🗨️ Commentaire [{langue}/{intention}] → {reponse[:60]}... ({temps:.1f}s)")


# ─── Gestion réaction ───────────────────────────────────────
async def _gerer_reaction(value: dict) -> None:
    verb = value.get("verb", "")

    if verb != "add":
        return

    post_id = value.get("post_id", "")
    reaction_type = value.get("reaction_type", "like")

    if not post_id:
        return

    if post_id in _reactions_traitees:
        return

    _reactions_traitees.add(post_id)

    remerciements = {
        "like": "Merci pour le soutien ! Ça fait plaisir de voir que le contenu vous parle 🙏",
        "love": "Wow, merci pour tout cet amour ! Vous êtes la meilleure communauté 🤖❤️",
        "haha": "Content que ça vous fasse rire ! Le code c'est aussi de l'humour 😄⚡",
        "wow": "Merci ! La tech n'a pas fini de nous surprendre 🤯🔬",
        "sad": "Merci pour votre soutien 💙 On traverse ça ensemble.",
        "angry": "Merci pour votre retour. On s'améliore chaque jour 🙏",
        "care": "Merci pour votre bienveillance ! La communauté Nyavodroid est forte 🤝💚",
    }

    texte = remerciements.get(
        reaction_type,
        "Merci pour votre réaction ! Restez connectés pour plus de contenu 🚀",
    )

    try:
        await commenter_post(post_id, texte)

        log_interaction(
            user_id="",
            type_interaction="reaction",
            langue="fr",
            intention="remerciement",
            temps_reponse=0.0,
            post_id=post_id,
        )

        print(f"👍 Réaction [{reaction_type}] sur {post_id} → remerciement posté")

    except Exception as e:
        print(f"⚠️ Erreur remerciement réaction : {e}")


# ─── Route SEON : envoyer une alerte Messenger ──────────────
@app.post("/alert")
async def receive_seon_alert(payload: AlertPayload, request: Request):
    now = time.time()

    # Nettoyage du rate limit
    while _alert_timestamps and now - _alert_timestamps[0] > 60:
        _alert_timestamps.pop(0)

    if len(_alert_timestamps) >= _MAX_ALERTS_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail="Trop d'alertes reçues. Réessaie dans une minute.",
        )

    if not SEON_ALERT_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="SEON_ALERT_TOKEN non configuré sur Railway.",
        )

    header_token = request.headers.get("x-alert-token", "")

    if not header_token or not secrets.compare_digest(SEON_ALERT_TOKEN, header_token):
        raise HTTPException(
            status_code=401,
            detail="Token d'alerte invalide.",
        )

    if not OWNER_PSID:
        raise HTTPException(
            status_code=503,
            detail="OWNER_PSID non configuré sur Railway.",
        )

    message = (payload.message or "").strip()

    if not message:
        raise HTTPException(
            status_code=422,
            detail="Le champ 'message' est vide.",
        )

    if len(message) > 1800:
        message = message[:1800] + "..."

    texte_alerte = f"🚨 ALERTE SEON\n\n{message}"

    _alert_timestamps.append(now)

    success = await repondre_message(OWNER_PSID, texte_alerte)

    if success:
        return {
            "status": "ok",
            "sent_to": OWNER_PSID,
        }

    raise HTTPException(
        status_code=502,
        detail="Échec de l'envoi Messenger. Vérifie OWNER_PSID et la fenêtre de 24h.",
    )


# ─── Health check ───────────────────────────────────────────
@app.get("/")
async def health():
    return {
        "status": "ok",
        "bot": BOT_NAME,
        "version": "3.1-SEON-Alert",
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)