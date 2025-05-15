import discord
from discord import app_commands
import os
import subprocess
import sqlite3
import datetime
import tempfile
import json
import logging

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('music_bot')

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("DISCORD_OWNER_ID", "0"))
MUSIC_DIR = os.getenv("MUSIC_DIR", "/music")
DB_FILE = "botdata.db"

# --- DISCORD CLIENT ---
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# --- DATABASE SETUP ---
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                user_id INTEGER PRIMARY KEY
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                link TEXT,
                title TEXT,
                size TEXT,
                duration TEXT,
                timestamp TEXT
            )
        """)
        c.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (OWNER_ID,))
        conn.commit()
    logger.info("Database initialized with tables 'whitelist' and 'uploads'.")

# --- DATABASE HELPERS ---
def add_to_whitelist(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (user_id,))
        conn.commit()
    logger.info(f"Added {user_id} to whitelist.")

def remove_from_whitelist(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM whitelist WHERE user_id = ?", (user_id,))
        conn.commit()
    logger.info(f"Removed {user_id} from whitelist.")

def is_whitelisted(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (user_id,))
        ok = cur.fetchone() is not None
    logger.debug(f"whitelist check {user_id}: {ok}")
    return ok

def save_upload(user_id, link, title, size, duration):
    ts = datetime.datetime.now().isoformat()
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO uploads (user_id, link, title, size, duration, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, link, title, size, duration, ts)
        )
        conn.commit()
    logger.info(f"Saved upload: {title} by {user_id}, size={size}, duration={duration}")

def get_upload_history(limit=10):
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.execute("SELECT user_id, title, size, duration, timestamp FROM uploads ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
    logger.info(f"Fetched {len(rows)} uploads.")
    return rows

# --- COMMANDS ---
@tree.command(name="upload_link", description="Download media from URL")
@app_commands.describe(link="URL to download (Spotify, SoundCloud, YouTube)")
async def upload_link(interaction, link: str):
    logger.info(f"upload_link invoked by {interaction.user.id}: {link}")
    if not is_whitelisted(interaction.user.id):
        logger.warning(f"unauthorized upload_link by {interaction.user.id}")
        await interaction.response.send_message("You are not whitelisted.", ephemeral=True)
        return
    await interaction.response.send_message(f"🔗 Download started: {link}")
    try:
        before = set(os.listdir(MUSIC_DIR))
        title = "Unknown"
        size = "? MB"
        duration = "?"
        if "spotify.com" in link:
            logger.info("Using spotdl for Spotify link")
            proc = subprocess.run(["spotdl", link, "--output", MUSIC_DIR], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"spotdl exit {proc.returncode}")
            out = proc.stdout.decode() if proc.stdout else ''
            err = proc.stderr.decode() if proc.stderr else ''
            logger.debug(f"spotdl stdout: {out}")
            logger.debug(f"spotdl stderr: {err}")
            after = set(os.listdir(MUSIC_DIR))
            new = after - before
            if new:
                fname = new.pop()
                filepath = os.path.join(MUSIC_DIR, fname)
                title = os.path.splitext(fname)[0]
                size = f"{round(os.path.getsize(filepath)/1024/1024,2)} MB"
                logger.info(f"Detected new file: {filepath}")
            else:
                logger.warning("No new file found after spotdl run")
        else:
            logger.info("Using yt-dlp for non-Spotify link")
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp:
                proc = subprocess.run([
                    "yt-dlp", "--dump-json", "-x", "--audio-format", "mp3", 
                    "-o", f"{MUSIC_DIR}/%(title)s.%(ext)s", link
                ], stdout=tmp, stderr=subprocess.PIPE)
            logger.info(f"yt-dlp exit {proc.returncode}")
            tmp.seek(0)
            try:
                data = json.load(open(tmp.name))
                title = data.get('title', title)
                duration = f"{round(data.get('duration',0)/60,2)} min"
                size_val = data.get('filesize') or 0
                size = f"{round(size_val/1024/1024,2)} MB"
                logger.info(f"Parsed metadata: {title}, {duration}, {size}")
            except Exception as e:
                logger.error(f"Failed parse yt-dlp JSON: {e}")
        # verify file
        expected = os.path.join(MUSIC_DIR, f"{title}.mp3")
        if title != "Unknown" and not os.path.exists(expected):
            logger.warning(f"Expected file missing: {expected}")
        save_upload(interaction.user.id, link, title, size, duration)
        await interaction.followup.send("✅ Download finished.")
    except Exception as e:
        logger.exception("Error in upload_link")
        await interaction.followup.send(f"❌ Download failed: {e}")

# rest of commands unchanged...

@client.event
async def on_ready():
    init_db()
    await tree.sync()
    logger.info(f"Bot ready as {client.user}")

client.run(TOKEN)
