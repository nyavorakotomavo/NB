#!/usr/bin/env python3
"""
NB — Rapport analytics quotidien (GitHub Actions, 23h UTC).
"""
import os
import sys

# Ajouter le parent au path pour importer bot/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.analytics import rapport_quotidien


def main() -> None:
    print(rapport_quotidien())


if __name__ == "__main__":
    main()