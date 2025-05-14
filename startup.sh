#!/bin/bash

REPO="Tikomatura/navidrome-discordbot"
CLONE_PATH="/app/code"

if [ -d "$CLONE_PATH/.git" ]; then
    echo "🔁 Pulling latest code from GitHub..."
    cd "$CLONE_PATH"
    git fetch origin main
    git reset --hard origin/main || { echo "❌ Git reset failed."; exit 1; }
else
    echo "⬇️ Cloning fresh repo..."
    git clone https://github.com/$REPO.git "$CLONE_PATH" || { echo "❌ Git clone failed."; exit 1; }
    cd "$CLONE_PATH"
fi

echo "🧾 Git version: $(git log -1 --pretty=format:'%h - %s (%ci)')"

echo "▶️ Starting bot..."
python bot.py
