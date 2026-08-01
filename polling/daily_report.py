#!/usr/bin/env python3
"""
NB — Rapport analytics quotidien (GitHub Actions, 23h UTC).
"""
import os
import sys

# Ajouter le parent au path pour importer bot/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.config import SUPABASE_URL, SUPABASE_KEY

# === VÉRIFICATION DES VARIABLES ===
if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Variables Supabase manquantes. Arrêt du rapport.")
    sys.exit(0)

if not SUPABASE_URL.startswith("https://"):
    print(f"❌ URL Supabase invalide : {SUPABASE_URL}")
    sys.exit(1)

try:
    from bot.analytics import rapport_quotidien
except ImportError as e:
    print(f"❌ Erreur d'import : {e}")
    sys.exit(1)


def main() -> None:
    try:
        resultat = rapport_quotidien()
        print(resultat)
    except Exception as e:
        print(f"❌ Erreur lors du rapport : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()