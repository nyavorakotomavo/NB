"""
NB — Configuration centrale.
Toutes les variables viennent de l'environnement (Railway / GitHub Secrets).
"""
import os


def _clean(val: str) -> str:
    return val.encode("ascii", "ignore").decode("ascii").strip()


# ── Facebook ──
FB_PAGE_ID = _clean(os.environ["FB_PAGE_ID"])
FB_PAGE_ACCESS_TOKEN = _clean(os.environ["FB_PAGE_ACCESS_TOKEN"])
FB_APP_SECRET = _clean(os.environ["FB_APP_SECRET"])
FB_VERIFY_TOKEN = _clean(os.environ["FB_VERIFY_TOKEN"])
GRAPH_VERSION = "v25.0"

# ── IA ──
MISTRAL_API_KEY = _clean(os.environ.get("MISTRAL_API_KEY", ""))
GEMINI_API_KEY = _clean(os.environ["GEMINI_API_KEY_BOT"])
GEMINI_TEXT_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-2.5-flash-lite:generateContent"
)
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

# ── Supabase ──
SUPABASE_URL = _clean(os.environ["SUPABASE_URL"])
SUPABASE_KEY = _clean(os.environ["SUPABASE_KEY"])

# ── Bot ──
BOT_NAME = "NB"
MAX_HISTORY_TURNS = 10
REQUEST_TIMEOUT = 30

# ── Emojis par thème ──
EMOJIS_PAR_THEME = {
    "code": ["💻", "⌨️", "🔧", "🧩", "⚙️"],
    "ia": ["🤖", "🧠", "✨", "🔮", "⚡"],
    "science": ["🔬", "🧪", "🌌", "🔭", "⚛️"],
    "securite": ["🔒", "🛡️", "🕵️", "🔐", "👁️"],
    "general": ["🚀", "💡", "🔥", "⭐", "🎯"],
    "remerciement": ["🙏", "❤️", "🤝", "😊", "👋"],
    "question": ["🤔", "❓", "💭", "🧐", "👀"],
}
