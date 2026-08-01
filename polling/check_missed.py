#!/usr/bin/env python3
"""
NB — Polling backup (GitHub Actions, toutes les 10 min).
Vérifie les messages/commentaires manqués par le webhook.
"""
import os
import sys
import time

import requests

FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
FB_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
GRAPH = "v25.0"
BASE = f"https://graph.facebook.com/{GRAPH}"

# === VÉRIFICATION : Si pas de variables, on sort silencieusement ===
if not FB_PAGE_ID or not FB_TOKEN:
    print("❌ Variables Facebook manquantes. Arrêt du polling.")
    sys.exit(0)


def get_conversations_sans_reponse() -> list[dict]:
    """Récupère les conversations Messenger sans réponse récente."""
    try:
        resp = requests.get(
            f"{BASE}/{FB_PAGE_ID}/conversations",
            params={
                "access_token": FB_TOKEN,
                "fields": "id,messages.limit(2){message,from,created_time}",
                "limit": 20,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as e:
        print(f"Erreur conversations : {e}")
        return []


def main() -> None:
    print("=" * 50)
    print(f"🔍 {os.environ.get('BOT_NAME', 'NB')} — Vérification des manqués")
    print("=" * 50)

    conversations = get_conversations_sans_reponse()

    if not conversations:
        print("  ✅ Aucune conversation en attente.")
        return

    manques = 0
    for conv in conversations:
        messages = conv.get("messages", {}).get("data", [])
        if not messages:
            continue

        dernier = messages[0]
        dernier_auteur = dernier.get("from", {}).get("id", "")

        # Si le dernier message n'est PAS de la Page → pas de réponse
        if dernier_auteur != FB_PAGE_ID:
            manques += 1
            print(f"  ⚠️  Conversation {conv['id']} sans réponse.")

    if manques == 0:
        print("  ✅ Toutes les conversations ont une réponse.")
    else:
        print(f"  📌 {manques} conversation(s) en attente.")


if __name__ == "__main__":
    main()