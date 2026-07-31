"""
NB — Analytics et détection de tendances.
"""
from datetime import datetime, timezone, timedelta

from supabase import create_client, Client

from bot.config import SUPABASE_URL, SUPABASE_KEY


def _get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def rapport_quotidien() -> str:
    """Génère un rapport texte des interactions des dernières 24h."""
    client = _get_client()
    hier = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    result = (
        client.table("interactions")
        .select("type, langue, intention")
        .gte("created_at", hier)
        .execute()
    )

    data = result.data
    if not data:
        return "📊 Aucune interaction dans les dernières 24h."

    total = len(data)
    par_type: dict[str, int] = {}
    par_langue: dict[str, int] = {}
    par_intention: dict[str, int] = {}

    for row in data:
        par_type[row["type"]] = par_type.get(row["type"], 0) + 1
        par_langue[row["langue"]] = par_langue.get(row["langue"], 0) + 1
        par_intention[row["intention"]] = par_intention.get(row["intention"], 0) + 1

    lignes = [
        f"📊 Rapport NB — dernières 24h",
        f"{'=' * 40}",
        f"Total interactions : {total}",
        "",
        "Par type :",
    ]
    for t, c in sorted(par_type.items(), key=lambda x: -x[1]):
        lignes.append(f"  {t} : {c}")

    lignes.append("")
    lignes.append("Par langue :")
    for l, c in sorted(par_langue.items(), key=lambda x: -x[1]):
        lignes.append(f"  {l} : {c}")

    lignes.append("")
    lignes.append("Par intention :")
    for i, c in sorted(par_intention.items(), key=lambda x: -x[1]):
        lignes.append(f"  {i} : {c}")

    return "\n".join(lignes)