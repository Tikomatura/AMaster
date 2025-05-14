# Selfhosted Discord Music Downloader Bot

A lightweight, containerized Discord bot that allows whitelisted users to submit music links or upload audio files via Discord. It downloads and stores audio in a shared volume, making it usable with any media server such as [Navidrome](https://www.navidrome.org/), Jellyfin, or Plex — or just as a personal collection.

---

## 🎯 Features

- `/upload <link>` — download audio from YouTube, Spotify, SoundCloud, etc.
- `/upload list` — list recent uploads with metadata (user, title, size, duration)
- `/whitelist add/remove <@user or user_id>` — only the bot owner can manage access
- `/whitelist list` — see all currently whitelisted user IDs
- Downloads are saved in a configurable `/music` directory
- Whitelist and upload history are stored using a local SQLite database

---

## ⚙️ Environment Setup

Create a `.env` file (not tracked in Git) in the root of your stack:

```env
DISCORD_TOKEN=your_discord_bot_token
DISCORD_OWNER_ID=your_discord_user_id
```

Optional environment variable:
```env
MUSIC_DIR=/music  # Path where downloaded files are stored
```

---

## 🐳 Docker Setup

This bot is designed to run standalone in Docker or Docker Compose. It pulls the latest code from GitHub on each container start.

### Example `docker-compose.yml`

```yaml
services:
  discordbot:
    build:
      context: https://github.com/Tikomatura/navidrome-discordbot.git
      dockerfile: Dockerfile
    container_name: discordbot
    restart: unless-stopped
    user: "999:993"
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - DISCORD_OWNER_ID=${DISCORD_OWNER_ID}
    volumes:
      - /srv/docker/music:/music
    working_dir: /app/code
```

---

## 🧠 How It Works

- On container start, the image runs `startup.sh` which:
  - Pulls the latest version of this repo from GitHub
  - Installs Python dependencies
  - Launches the bot
- The bot accepts Discord slash commands via **Direct Messages**
- Only users in the whitelist (managed via slash commands) may upload links or files

---

## 📦 Dependencies

- `discord.py`
- `yt-dlp`
- `spotdl`
- `ffmpeg` (preinstalled in the Docker image)

---

## 🔐 Security Notes

- The bot uses slash commands with strict access control
- Only the owner (via `DISCORD_OWNER_ID`) can modify the whitelist or view upload history
- No tokens or credentials are stored in the GitHub repo

---

## 📁 Persistent Data

- `botdata.db`: stores whitelist and upload history (SQLite)
- `/music/`: shared volume where audio is downloaded

---

## 🧪 Example Commands (in Discord)

```
/upload https://www.youtube.com/watch?v=xyz123
/whitelist add 123456789012345678
/whitelist list
/upload list
```

---

## ✅ License

MIT — use freely, contribute via GitHub if you’d like to improve the project.
