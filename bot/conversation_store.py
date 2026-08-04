"""
NB — Stockage des conversations (Supabase).
Historique multi-tours + analytics.
CORRECTION : ordre chronologique correct pour le contexte.
"""
from datetime import datetime, timezone
from supabase import create_client, Client
from bot.config import SUPABASE_URL, SUPABASE_KEY, MAX_HISTORY_TURNS

_client: Client | None = None

def _get_client() -> Client:
    """Retourne le client Supabase avec vérification."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise Exception("❌ Supabase non configuré (URL ou KEY manquante)")
        if not SUPABASE_URL.startswith("https://"):
            raise Exception(f"❌ URL Supabase invalide : {SUPABASE_URL}")
        print(f"🔗 Connexion à Supabase : {SUPABASE_URL[:30]}...")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Connexion Supabase établie")
    return _client

def sauvegarder_message(
    user_id: str,
    platform: str,
    role: str,
    contenu: str,
    langue: str,
    post_id: str = "",
) -> None:
    """Sauvegarde un message dans l'historique."""
    try:
        client = _get_client()
        client.table("conversations").insert({
            "user_id": user_id,
            "platform": platform,
            "role": role,
            "contenu": contenu,
            "langue": langue,
            "post_id": post_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        print(f"⚠️  Erreur sauvegarde message : {e}")

def get_historique(user_id: str, platform: str) -> list[dict]:
    """
    Récupère les 10 derniers tours de conversation (20 messages).
    CORRECTION : ordre ASC pour garder le contexte chronologique correct.
    """
    try:
        client = _get_client()
        result = (
            client.table("conversations")
            .select("role, contenu, langue, created_at")
            .eq("user_id", user_id)
            .eq("platform", platform)
            .order("created_at", asc=True)  # ✅ CORRECTION : ordre chronologique
            .limit(MAX_HISTORY_TURNS * 2)
            .execute()
        )
        historique = result.data  # ✅ Déjà dans le bon ordre
        print(f"📚 Historique récupéré : {len(historique)} messages pour {user_id}")
        return historique
    except Exception as e:
        print(f"⚠️  Erreur récupération historique : {e}")
        return []

def log_interaction(
    user_id: str,
    type_interaction: str,
    langue: str,
    intention: str,
    temps_reponse: float,
    post_id: str = "",
) -> None:
    """Log une interaction pour les analytics."""
    try:
        client = _get_client()
        client.table("interactions").insert({
            "user_id": user_id,
            "type": type_interaction,
            "langue": langue,
            "intention": intention,
            "temps_reponse": temps_reponse,
            "post_id": post_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        print(f"⚠️  Erreur log interaction : {e}") 