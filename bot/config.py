"""
NB — Configuration et variables d'environnement.
Toutes les clés API et tokens sont chargés depuis l'environnement.
"""
import os
import re


def _clean(value: str) -> str:
    """Nettoie une valeur d'environnement (supprime les espaces, retours à la ligne)."""
    if not value:
        return ""
    return re.sub(r'[\r\n\s]+', '', value).strip()


# ─── Facebook ──────────────────────────────────
FB_PAGE_ID = _clean(os.environ.get("FB_PAGE_ID", ""))
FB_PAGE_ACCESS_TOKEN = _clean(os.environ.get("FB_PAGE_ACCESS_TOKEN", ""))
FB_VERIFY_TOKEN = _clean(os.environ.get("FB_VERIFY_TOKEN", ""))
FB_APP_SECRET = _clean(os.environ.get("FB_APP_SECRET", ""))

# ─── IA ────────────────────────────────────────
MISTRAL_API_KEY = _clean(os.environ.get("MISTRAL_API_KEY", ""))
# Note : le nom exact dans Railway est GEMINI_APP_KEY_BOT
GEMINI_API_KEY = _clean(os.environ.get("GEMINI_APP_KEY_BOT", ""))
# Fallback si le nom est différent
if not GEMINI_API_KEY:
    GEMINI_API_KEY = _clean(os.environ.get("GEMINI_API_KEY_BOT", ""))

# ─── Supabase ──────────────────────────────────
SUPABASE_URL = _clean(os.environ.get("SUPABASE_URL", ""))
SUPABASE_KEY = _clean(os.environ.get("SUPABASE_KEY", ""))

# ─── Bot ──────────────────────────────────────
BOT_NAME = _clean(os.environ.get("BOT_NAME", "Nyavo Bot"))
PORT = int(os.environ.get("PORT", 8080))

# ─── URLs API ──────────────────────────────────
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
GEMINI_TEXT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# ─── Timeouts ──────────────────────────────────
REQUEST_TIMEOUT = 30.0  # secondes
MAX_HISTORY_TURNS = 10  # nombre de tours conservés par utilisateur

# ─── Graph API ─────────────────────────────────
GRAPH_VERSION = "v26.0"

# ─── Vérification pour GitHub Actions ─────────
if not FB_PAGE_ID:
    print("⚠️  Mode GitHub Actions : variables non chargées (mode dégradé)")