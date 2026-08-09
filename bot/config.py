"""
NB — Configuration et variables d'environnement.
Toutes les clés API et tokens sont chargés depuis l'environnement.
"""

import os
import re
import unicodedata
from datetime import datetime


def _clean_secret(value: str) -> str:
    """Nettoie un secret/token/ID (supprime espaces et caractères invisibles)."""
    if not value:
        return ""

    value = ''.join(
        ch for ch in value
        if unicodedata.category(ch)[0] not in ["C", "Z"]
    )

    value = re.sub(r'[\u200e\u200f\u202a-\u206e\u2066-\u2069]', '', value)
    value = re.sub(r'[\r\n\t\s]+', '', value)

    return value.strip()


def _clean_text(value: str) -> str:
    """Nettoie un texte normal (garde les espaces utiles)."""
    if not value:
        return ""

    value = ''.join(
        ch for ch in value
        if unicodedata.category(ch)[0] != "C" or ch in "\n\t "
    )

    value = re.sub(r'[\u200e\u200f\u202a-\u206e\u2066-\u2069]', '', value)
    value = re.sub(r'\s+', ' ', value)

    return value.strip()


# ─── Facebook ────────────────────────────────────────────────
FB_PAGE_ID = _clean_secret(os.environ.get("FB_PAGE_ID", ""))
FB_PAGE_ACCESS_TOKEN = _clean_secret(os.environ.get("FB_PAGE_ACCESS_TOKEN", ""))
FB_VERIFY_TOKEN = _clean_secret(os.environ.get("FB_VERIFY_TOKEN", ""))
FB_APP_SECRET = _clean_secret(os.environ.get("FB_APP_SECRET", ""))


# ─── SEON / Alertes ──────────────────────────────────────────
OWNER_PSID = _clean_secret(os.environ.get("OWNER_PSID", ""))
SEON_ALERT_TOKEN = _clean_secret(os.environ.get("SEON_ALERT_TOKEN", ""))


# ─── IA ─────────────────────────────────────────────────────
MISTRAL_API_KEY = _clean_secret(os.environ.get("MISTRAL_API_KEY", ""))

GEMINI_API_KEY = _clean_secret(os.environ.get("GEMINI_APP_KEY_BOT", ""))

if not GEMINI_API_KEY:
    GEMINI_API_KEY = _clean_secret(os.environ.get("GEMINI_API_KEY_BOT", ""))

if not GEMINI_API_KEY:
    GEMINI_API_KEY = _clean_secret(os.environ.get("GEMINI_API_KEY", ""))


# ─── Supabase ────────────────────────────────────────────────
SUPABASE_URL = _clean_secret(os.environ.get("SUPABASE_URL", ""))
SUPABASE_KEY = _clean_secret(os.environ.get("SUPABASE_KEY", ""))

if not SUPABASE_URL:
    SUPABASE_URL = "https://efchirndbidiyzwezkgt.supabase.co"
    print("⚠️ SUPABASE_URL manquant, utilisation de l'URL en dur")

if not SUPABASE_KEY:
    print("❌ ERREUR CRITIQUE : SUPABASE_KEY manquante !")


# ─── Bot ─────────────────────────────────────────────────────
BOT_NAME = _clean_text(os.environ.get("BOT_NAME", "Nyavo Bot"))

try:
    PORT = int(os.environ.get("PORT", "8080") or 8080)
except ValueError:
    PORT = 8080


# ─── URLs API ────────────────────────────────────────────────
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
GEMINI_TEXT_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"


# ─── Timeouts ────────────────────────────────────────────────
REQUEST_TIMEOUT = 30.0
MAX_HISTORY_TURNS = 10


# ─── Graph API ───────────────────────────────────────────────
GRAPH_VERSION = "v26.0"


# ─── VÉRITÉ TERRAIN ─────────────────────────────────────────
PAGE_OFFRE_REELLE = """
CE QUE LA PAGE OFFRE RÉELLEMENT :
Contenu gratuit : posts tech, stories, anecdotes dev.
Pas de lives payants pour l'instant.
Pas d'abonnement payant pour l'instant.
Pas de produits à vendre pour l'instant.
Communauté gratuite autour de la tech/dev.
Réponses humaines aux questions.
"""


# ─── Date actuelle ───────────────────────────────────────────
def get_current_date() -> str:
    jours = [
        "lundi",
        "mardi",
        "mercredi",
        "jeudi",
        "vendredi",
        "samedi",
        "dimanche",
    ]

    mois = [
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ]

    now = datetime.now()

    return f"{jours[now.weekday()]} {now.day} {mois[now.month - 1]} {now.year}"


# ─── Vérification au démarrage ──────────────────────────────
print("=" * 50)
print("🔧 CONFIGURATION CHARGÉE")
print(f"  ✅ FB_PAGE_ID: {FB_PAGE_ID[:10] if FB_PAGE_ID else 'NON DÉFINI'}...")
print(f"  ✅ SUPABASE_URL: {SUPABASE_URL[:30] if SUPABASE_URL else 'NON DÉFINI'}...")
print(f"  ✅ SUPABASE_KEY: {'PRÉSENT' if SUPABASE_KEY else 'NON DÉFINI'}")
print(f"  ✅ MISTRAL_API_KEY: {'PRÉSENT' if MISTRAL_API_KEY else 'NON DÉFINI'}")
print(f"  ✅ GEMINI_API_KEY: {'PRÉSENT' if GEMINI_API_KEY else 'NON DÉFINI'}")
print(f"  ✅ OWNER_PSID: {'PRÉSENT' if OWNER_PSID else 'NON DÉFINI'}")
print(f"  ✅ SEON_ALERT_TOKEN: {'PRÉSENT' if SEON_ALERT_TOKEN else 'NON DÉFINI'}")
print(f"  📅 Date actuelle: {get_current_date()}")
print("=" * 50)