#!/bin/bash

REPO="Tikomatura/navidrome-discordbot"
CLONE_PATH="/app/code"

if [ -d "$CLONE_PATH/.git" ]; then
    echo "🔁 Pulling latest code..."
    cd "$CLONE_PATH"
    git pull
else
    echo "⬇️ Cloning public repo..."
    git clone https://github.com/$REPO.git "$CLONE_PATH"
fi

cd "$CLONE_PATH"

echo "▶️ Starting bot..."
python bot.py
