#!/usr/bin/env python3
"""
NB — Rapport analytics quotidien (GitHub Actions, 23h UTC).
"""
import os
import sys

# Ajouter le parent au path pour importer bot/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.analytics import rapport_quotidien

# === AJOUT : Vérification pour GitHub Actions (ne supprime rien) ===
from bot.config import SUPABASE_URL, SUPABASE_KEY

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Variables Supabase manquantes. Arrêt du rapport.")
    sys.exit(0)


def main() -> None:
    print(rapport_quotidien())


if __name__ == "__main__":
    main()