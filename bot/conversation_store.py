"""
NB — Stockage des conversations (Supabase).
Historique multi-tours + analytics.
"""
from datetime import datetime, timezone

from supabase import create_client, Client

from bot.config import SUPABASE_URL, SUPABASE_KEY, MAX_HISTORY_TURNS

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def initialiser_tables() -> None:
    """
    Crée les tables si elles n'existent pas.
    À appeler une fois au démarrage du serveur.
    Note : les tables sont créées via le SQL ci-dessous.
    """
    # Les tables doivent être créées manuellement dans Supabase.
    # Voir le SQL dans la documentation de déploiement.
    pass


def sauvegarder_message(
    user_id: str,
    platform: str,
    role: str,
    contenu: str,
    langue: str,
    post_id: str = "",
) -> None:
    """Sauvegarde un message dans l'historique."""
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


def get_historique(user_id: str, platform: str) -> list[dict]:
    """Récupère les N derniers messages d'un utilisateur."""
    client = _get_client()
    result = (
        client.table("conversations")
        .select("role, contenu, langue, created_at")
        .eq("user_id", user_id)
        .eq("platform", platform)
        .order("created_at", desc=True)
        .limit(MAX_HISTORY_TURNS)
        .execute()
    )
    # Inverser pour avoir l'ordre chronologique
    return list(reversed(result.data))


def log_interaction(
    user_id: str,
    type_interaction: str,
    langue: str,
    intention: str,
    temps_reponse: float,
    post_id: str = "",
) -> None:
    """Log une interaction pour les analytics."""
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