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
logger = logging.getLogger('music_bot v0.2')

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("DISCORD_OWNER_ID", "0"))
MUSIC_DIR = os.getenv("MUSIC_DIR", "/music")
DB_FILE = "botdata.db"
COOKIES_PATH = os.getenv("COOKIES_PATH", ".yt_cookies.txt")

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

# --- HELPER FUNCTIONS ---
def add_to_whitelist(user_id: int):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (user_id,))
        conn.commit()
    logger.info(f"Added user {user_id} to whitelist.")

def remove_from_whitelist(user_id: int):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM whitelist WHERE user_id = ?", (user_id,))
        conn.commit()
    logger.info(f"Removed user {user_id} from whitelist.")

def list_whitelisted_users() -> list:
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM whitelist")
        rows = c.fetchall()
    user_ids = [r[0] for r in rows]
    logger.info(f"Current whitelist: {user_ids}")
    return user_ids


def is_whitelisted(user_id: int) -> bool:
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (user_id,))
        return c.fetchone() is not None


def save_upload(user_id: int, link: str, title: str, size: str, duration: str):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO uploads (user_id, link, title, size, duration, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, link, title, size, duration, datetime.datetime.now().isoformat())
        )
        conn.commit()
    logger.info(f"Saved upload: user_id={user_id}, title={title}, size={size}, duration={duration}, link={link}")


def get_upload_history(limit: int = 10) -> list:
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, title, size, duration, timestamp FROM uploads ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = c.fetchall()
    logger.info(f"Fetched last {limit} uploads.")
    return rows

# --- UTILITY: RECURSIVE FILE LIST ---
def list_all_files(root_dir: str) -> set:
    files = set()
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            files.add(os.path.join(dirpath, f))
    return files

# --- SLASH COMMANDS ---
@tree.command(name="whitelist", description="Manage the whitelist")
@app_commands.describe(action="add/remove/list", user="User to modify (only for add/remove)")
async def whitelist_cmd(interaction: discord.Interaction, action: str, user: discord.User = None):
    logger.info(f"Whitelist command by {interaction.user.id}: action={action}, target={getattr(user, 'id', None)}")
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Only the bot owner can manage the whitelist.", ephemeral=True)
        return
    action = action.lower()
    if action == "add":
        if not user:
            await interaction.response.send_message("Please specify a user.", ephemeral=True)
            return
        add_to_whitelist(user.id)
        await interaction.response.send_message(f"User <@{user.id}> added to whitelist.")
    elif action == "remove":
        if not user:
            await interaction.response.send_message("Please specify a user.", ephemeral=True)
            return
        remove_from_whitelist(user.id)
        await interaction.response.send_message(f"User <@{user.id}> removed from whitelist.")
    elif action == "list":
        ids = list_whitelisted_users()
        mentions = ", ".join(f"<@{uid}>" for uid in ids) or "(empty)"
        await interaction.response.send_message(f"Current whitelist: {mentions}")
    else:
        await interaction.response.send_message("Action must be 'add', 'remove', or 'list'.", ephemeral=True)

upload_group = app_commands.Group(name="upload", description="Manage uploads")
tree.add_command(upload_group)

@upload_group.command(name="link", description="Submit a media link to download")
@app_commands.describe(link="Media URL to download")
async def upload_link(interaction: discord.Interaction, link: str):
    logger.info(f"Upload link by {interaction.user.id}: {link}")
    if not is_whitelisted(interaction.user.id):
        await interaction.response.send_message("You are not whitelisted.", ephemeral=True)
        return
    await interaction.response.send_message(f"🔗 Download started: {link}")
    try:
        before = list_all_files(MUSIC_DIR)
        # Spotify via spotdl
        if "spotify.com" in link:
            logger.info("Spotify download via spotdl")
            proc = subprocess.run([
                "spotdl", "download", link,
                "--output", MUSIC_DIR,
                "--log-level", "DEBUG",
                "--cookie-file", COOKIES_PATH
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode != 0:
                err = proc.stderr.decode(errors="ignore")
                logger.error(f"spotdl failed ({proc.returncode}): {err}")
                await interaction.followup.send(f"❌ spotdl error:\n```\n{err}\n```")
                return
            logger.debug(f"spotdl stdout:\n{proc.stdout.decode(errors='ignore')}")
            logger.debug(f"spotdl stderr:\n{proc.stderr.decode(errors='ignore')}")
        # Other links via yt-dlp
        else:
            # Metadata extraction
            proc_meta = subprocess.run([
                "yt-dlp", "--dump-json", link
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc_meta.returncode != 0:
                err = proc_meta.stderr.decode(errors="ignore")
                logger.error(f"yt-dlp metadata failed ({proc_meta.returncode}): {err}")
                await interaction.followup.send(f"❌ yt-dlp metadata error:\n```\n{err}\n```")
                return
            meta = json.loads(proc_meta.stdout)
            title = meta.get("title", "Unknown")
            duration = f"{round(meta.get('duration', 0)/60, 2)} min"
            # Audio download
            proc_dl = subprocess.run([
                "yt-dlp", "-x", "--audio-format", "mp3",
                "-o", f"{MUSIC_DIR}/%(title)s.%(ext)s", link,
                "--cookies", COOKIES_PATH
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc_dl.returncode != 0:
                err = proc_dl.stderr.decode(errors="ignore")
                logger.error(f"yt-dlp download failed ({proc_dl.returncode}): {err}")
                await interaction.followup.send(f"❌ yt-dlp download error:\n```\n{err}\n```")
                return
        # Identify new file
        after = list_all_files(MUSIC_DIR)
        new_files = after - before
        mp3s = [f for f in new_files if f.lower().endswith('.mp3')]
        if not mp3s:
            logger.error(f"No new MP3 in {MUSIC_DIR}: {new_files}")
            await interaction.followup.send("❌ Download finished but no new file found.")
            return
        filepath = mp3s[0]
        filename = os.path.basename(filepath)
        size = f"{round(os.path.getsize(filepath)/1024/1024,2)} MB"
        # Duration fallback
        if 'duration' not in locals():
            duration = 'Unknown'
        save_upload(interaction.user.id, link, os.path.splitext(filename)[0], size, duration)
        await interaction.followup.send(f"✅ Download finished: `{filename}` ({size}, {duration})")
    except Exception as e:
        logger.exception(f"Download failed: {link}")
        await interaction.followup.send(f"❌ Download failed: {e}")

@upload_group.command(name="attachment", description="Upload an audio file (mp3, aac, opus)")
@app_commands.describe(file="Audio file to upload")
async def upload_attachment(interaction: discord.Interaction, file: discord.Attachment):
    logger.info(f"Upload attachment by {interaction.user.id}: {file.filename} ({file.size} bytes)")
    if not is_whitelisted(interaction.user.id):
        await interaction.response.send_message("You are not whitelisted.", ephemeral=True)
        return
    if not any(file.filename.lower().endswith(ext) for ext in [".mp3", ".aac", ".opus"]):
        await interaction.response.send_message("❌ Unsupported file type. Only MP3, AAC, OPUS allowed.", ephemeral=True)
        return
    dest = os.path.join(MUSIC_DIR, file.filename)
    await file.save(dest)
    size_str = f"{round(file.size/1024/1024,2)} MB"
    save_upload(interaction.user.id, file.url, file.filename, size_str, "Unknown")
    await interaction.response.send_message(f"✅ File uploaded: `{file.filename}`")

@upload_group.command(name="playlist", description="Download an entire playlist URL")
@app_commands.describe(link="Playlist URL to download")
async def upload_playlist(interaction: discord.Interaction, link: str):
    logger.info(f"Upload playlist by {interaction.user.id}: {link}")
    if not is_whitelisted(interaction.user.id):
        await interaction.response.send_message("You are not whitelisted.", ephemeral=True)
        return
    await interaction.response.send_message(f"📥 Playlist download started: {link}")
    try:
        proc = subprocess.run([
            "yt-dlp", "-x", "--audio-format", "mp3", "--yes-playlist",
            "-o", f"{MUSIC_DIR}/%(playlist_title)s/%(title)s.%(ext)s", link
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            err = proc.stderr.decode(errors="ignore")
            logger.error(f"Playlist download failed ({proc.returncode}): {err}")
            await interaction.followup.send(f"❌ Playlist error:\n```\n{err}\n```")
            return
        await interaction.followup.send("✅ Playlist download finished.")
    except Exception as e:
        logger.exception(f"Playlist download failed: {link}")
        await interaction.followup.send(f"❌ Playlist download failed: {e}")

@upload_group.command(name="list", description="Show latest uploads")
@app_commands.describe(limit="Number of items to show (max 20)")
async def upload_list(interaction: discord.Interaction, limit: int = 10):
    logger.info(f"Upload list by {interaction.user.id}, limit={limit}")
    if not is_whitelisted(interaction.user.id):
        await interaction.response.send_message("You are not whitelisted.", ephemeral=True)
        return
    limit = min(limit, 20)
    rows = get_upload_history(limit)
    embed = discord.Embed(title="Latest Uploads", color=0x00ff00)
    for user_id, title, size, duration, ts in rows:
        time = datetime.datetime.fromisoformat(ts).strftime('%Y-%m-%d %H:%M')
        embed.add_field(
            name=title,
            value=f"From: <@{user_id}> | Size: {size} | Duration: {duration} | {time}",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

@client.event
async def on_ready():
    init_db()
    if not getattr(client, 'commands_synced', False):
        await tree.sync()
        client.commands_synced = True
    logger.info(f"Bot ready as {client.user}")

client.run(TOKEN)
