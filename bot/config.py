"""
NB — Configuration et variables d'environnement.
Toutes les clés API et tokens sont chargés depuis l'environnement.
"""
import os
import re
import unicodedata
from datetime import datetime


def _clean(value: str) -> str:
    """Nettoie une valeur d'environnement (supprime les caractères invisibles)."""
    if not value:
        return ""
    value = ''.join(ch for ch in value if unicodedata.category(ch)[0] not in ['C', 'Z'])
    value = re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069]', '', value)
    value = re.sub(r'[\r\n\s]+', '', value)
    return value.strip()


# ─── Facebook ──────────────────────────────────
FB_PAGE_ID = _clean(os.environ.get("FB_PAGE_ID", ""))
FB_PAGE_ACCESS_TOKEN = _clean(os.environ.get("FB_PAGE_ACCESS_TOKEN", ""))
FB_VERIFY_TOKEN = _clean(os.environ.get("FB_VERIFY_TOKEN", ""))
FB_APP_SECRET = _clean(os.environ.get("FB_APP_SECRET", ""))

# ─── IA ────────────────────────────────────────
MISTRAL_API_KEY = _clean(os.environ.get("MISTRAL_API_KEY", ""))
GEMINI_API_KEY = _clean(os.environ.get("GEMINI_APP_KEY_BOT", ""))
if not GEMINI_API_KEY:
    GEMINI_API_KEY = _clean(os.environ.get("GEMINI_API_KEY_BOT", ""))

# ─── Supabase ──────────────────────────────────
SUPABASE_URL = _clean(os.environ.get("SUPABASE_URL", ""))
SUPABASE_KEY = _clean(os.environ.get("SUPABASE_KEY", ""))

if not SUPABASE_URL:
    SUPABASE_URL = "https://efchirndbidiyzwezkgt.supabase.co"
    print("⚠️  SUPABASE_URL manquant, utilisation de l'URL en dur")

# ─── Bot ──────────────────────────────────────
BOT_NAME = _clean(os.environ.get("BOT_NAME", "Nyavo Bot"))
PORT = int(os.environ.get("PORT", 8080))

# ─── URLs API ──────────────────────────────────
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
GEMINI_TEXT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# ─── Timeouts ──────────────────────────────────
REQUEST_TIMEOUT = 30.0
MAX_HISTORY_TURNS = 10  # 10 tours de conversation

# ─── Graph API ─────────────────────────────────
GRAPH_VERSION = "v26.0"


# ─── DATE ACTUELLE (pour le contexte) ─────────
def get_current_date() -> str:
    """Retourne la date actuelle au format 'lundi 2 août 2026'."""
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    now = datetime.now()
    return f"{jours[now.weekday()]} {now.day} {mois[now.month-1]} {now.year}"


# ─── Vérification au démarrage ────────────────
print("=" * 50)
print("🔧 CONFIGURATION CHARGEE")
print(f"  ✅ FB_PAGE_ID: {FB_PAGE_ID[:10] if FB_PAGE_ID else 'NON DEFINI'}...")
print(f"  ✅ SUPABASE_URL: {SUPABASE_URL[:30] if SUPABASE_URL else 'NON DEFINI'}...")
print(f"  ✅ SUPABASE_KEY: {'PRESENT' if SUPABASE_KEY else 'NON DEFINI'}")
print(f"  ✅ MISTRAL_API_KEY: {'PRESENT' if MISTRAL_API_KEY else 'NON DEFINI'}")
print(f"  ✅ GEMINI_API_KEY: {'PRESENT' if GEMINI_API_KEY else 'NON DEFINI'}")
print(f"  📅 Date actuelle: {get_current_date()}")
print("=" * 50)