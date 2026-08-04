"""
NB — Serveur FastAPI (webhook Facebook).
CORRECTIONS :
- UN SEUL message par tour (pas de rafale)
- Délai humain réaliste (15-45s selon longueur)
- Cache anti-doublon strict (60s)
- Pause café toutes les 3 réponses
"""
import time
import asyncio
import random
import os
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from bot.config import FB_VERIFY_TOKEN, BOT_NAME, FB_PAGE_ID
from bot.fb_client import (
    verifier_signature,
    envoyer_message_humain,
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

print("=" * 50)
print(f"🤖 {BOT_NAME} - Démarrage du serveur...")
print(f"📱 FB_PAGE_ID: {FB_PAGE_ID[:10] if FB_PAGE_ID else 'NON DEFINI'}...")
print(f"🔑 FB_VERIFY_TOKEN: {FB_VERIFY_TOKEN[:10] if FB_VERIFY_TOKEN else 'NON DEFINI'}...")
print(f"🌐 Port: {int(os.environ.get('PORT', 8080))}")
print("=" * 50)

app = FastAPI(title=f"{BOT_NAME} — Nyavodroid Bot")

_reactions_traitees: set[str] = set()
_derniers_traitements: dict[str, float] = {}
_CACHE_TRAITEMENT = 60.0  # 60 secondes entre deux traitements du même utilisateur

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

@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.body()
    print("📨 REQUETE POST RECUE")
    
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verifier_signature(body, signature):
        print("❌ Signature invalide")
        return Response(status_code=403)
    print("✅ Signature valide")
    
    data = await request.json()
    print(f"📦 Données reçues: {str(data)[:200]}...")
    
    compteur_utilisateurs = 0
    
    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_id = messaging.get("sender", {}).get("id", "")
            
            # 🚫 ANTI-SPAM : Un seul traitement par utilisateur par 60s
            if sender_id in _derniers_traitements:
                temps_ecoule = time.time() - _derniers_traitements[sender_id]
                if temps_ecoule < _CACHE_TRAITEMENT:
                    print(f"⏭️  Utilisateur {sender_id} déjà traité il y a {temps_ecoule:.0f}s, ignoré.")
                    continue
            
            print("💬 Message Messenger reçu")
            await _gerer_message(messaging)
            _derniers_traitements[sender_id] = time.time()
            compteur_utilisateurs += 1
            
            # Délai entre chaque utilisateur (8-15s)
            await asyncio.sleep(random.uniform(8.0, 15.0))
            
            # Pause café toutes les 3 réponses
            if compteur_utilisateurs % 3 == 0:
                print("☕ Pause café...")
                await asyncio.sleep(random.uniform(15.0, 25.0))
        
        for change in entry.get("changes", []):
            value = change.get("value", {})
            item = value.get("item", "")
            print(f"📌 Changement: {item}")
            
            if item == "comment":
                comment_id = value.get("comment_id", "")
                
                if comment_id in _derniers_traitements:
                    temps_ecoule = time.time() - _derniers_traitements[comment_id]
                    if temps_ecoule < _CACHE_TRAITEMENT:
                        print(f"⏭️  Commentaire {comment_id} déjà traité, ignoré.")
                        continue
                
                await _gerer_commentaire(value)
                _derniers_traitements[comment_id] = time.time()
                compteur_utilisateurs += 1
                await asyncio.sleep(random.uniform(8.0, 15.0))
                
                if compteur_utilisateurs % 3 == 0:
                    print("☕ Pause café...")
                    await asyncio.sleep(random.uniform(15.0, 25.0))
            
            elif item == "reaction":
                await _gerer_reaction(value)
    
    return {"status": "ok"}

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
    sauvegarder_message(sender_id, "messenger", "user", texte, langue)
    
    reponse = await generer_reponse(
        message=texte,
        langue=langue,
        intention=intention,
        historique=historique,
    )
    
    # ✅ UN SEUL MESSAGE avec délai humain
    await envoyer_message_humain(sender_id, reponse, type_envoi="message")
    
    sauvegarder_message(sender_id, "messenger", "bot", reponse, langue)
    
    temps = time.time() - t0
    log_interaction(sender_id, "message", langue, intention, temps)
    print(f"  💬 Messenger [{langue}/{intention}] → {reponse[:60]}... ({temps:.1f}s)")

async def _gerer_commentaire(value: dict) -> None:
    verb = value.get("verb", "")
    if verb != "add":
        return
    
    comment_id = value.get("comment_id", "")
    sender_id = value.get("from", {}).get("id", "")
    texte = value.get("message", "")
    post_id = value.get("post_id", "")
    
    if not comment_id or not texte:
        return
    
    print(f"🗨️  Commentaire de {sender_id}: {texte[:50]}...")
    t0 = time.time()
    
    langue = detecter_langue(texte)
    intention = analyser_intention(texte)
    
    if intention == "spam":
        print(f"🚫 Spam ignoré de {sender_id}")
        return
    
    contexte = await get_post_message(post_id) if post_id else ""
    historique = get_historique(sender_id, "comment")
    sauvegarder_message(sender_id, "comment", "user", texte, langue, post_id)
    
    reponse = await generer_reponse(
        message=texte,
        langue=langue,
        intention=intention,
        contexte_post=contexte,
        historique=historique,
    )
    
    await envoyer_message_humain(comment_id, reponse, type_envoi="commentaire")
    sauvegarder_message(sender_id, "comment", "bot", reponse, langue, post_id)
    
    temps = time.time() - t0
    log_interaction(sender_id, "commentaire", langue, intention, temps, post_id)
    print(f"  🗨️  Commentaire [{langue}/{intention}] → {reponse[:60]}... ({temps:.1f}s)")

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
        log_interaction("", "reaction", "fr", "remerciement", 0.0, post_id)
        print(f"  👍 Réaction [{reaction_type}] sur {post_id} → remerciement posté")
    except Exception as e:
        print(f"  ⚠️  Erreur remerciement réaction : {e}")

@app.get("/")
async def health():
    return {"status": "ok", "bot": BOT_NAME, "version": "2.0"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)