# Navidrome Discord Bot

A lightweight, containerized Discord bot that allows whitelisted users to submit music links or audio files via DM. The bot downloads audio to a shared `/music` volume, making it compatible with [Navidrome](https://www.navidrome.org/) or any Subsonic-compatible music server.

---

## 🎯 Features

- `/upload <link>` — download audio from YouTube, Spotify, SoundCloud, etc.
- `/upload_list` — list recent uploads with metadata (user, title, size, duration)
- `/whitelist add/remove <@user or user_id>` — only the bot owner can manage access
- `/whitelist list` — see all currently whitelisted user IDs
- Downloads are saved in the `/music` directory for Navidrome access
- Whitelist and upload history are stored using a local SQLite database

---

## ⚙️ Environment Setup

Create a `.env` file (not tracked in Git) in the root of your stack:

```env
DISCORD_TOKEN=your_discord_bot_token
DISCORD_OWNER_ID=your_discord_user_id
```

---

## 🐳 Docker Setup

This bot is designed to run alongside Navidrome in a Docker Compose stack. It pulls the latest code from GitHub on each start.

### Example `docker-compose.yml`

```yaml
services:
  discordbot:
    image: navidrome-discordbot:latest
    container_name: navidrome-discordbot
    restart: unless-stopped
    user: "999:993"
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - DISCORD_OWNER_ID=${DISCORD_OWNER_ID}
    volumes:
      - /srv/docker/navidrome/music:/music
    working_dir: /app
```

---

## 🧠 How It Works

- On container start, the image runs `startup.sh` which:
  - Pulls the latest version of this repo from GitHub
  - Installs Python dependencies
  - Launches the bot
- The bot accepts Discord slash commands only via **Direct Messages**
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
- `music/`: shared volume where audio is downloaded for Navidrome

---

## 🧪 Example Commands (in Discord)

```
/upload https://www.youtube.com/watch?v=xyz123
/whitelist add 123456789012345678
/whitelist list
/upload_list
```

---

## ✅ License

MIT — use freely, contribute via GitHub if you’d like to improve the project.
