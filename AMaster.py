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
        # Ensure owner is whitelisted
        c.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (OWNER_ID,))
        conn.commit()
    logger.info("Database initialized with tables 'whitelist' and 'uploads'.")

# --- DATABASE HELPER FUNCTIONS ---
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
        result = c.fetchone() is not None
    logger.debug(f"Whitelist check for {user_id}: {result}")
    return result


def save_upload(user_id: int, link: str, title: str, size: str, duration: str):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO uploads (user_id, link, title, size, duration, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, link, title, size, duration, datetime.datetime.now().isoformat()))
        conn.commit()
    logger.info(f"Saved upload: user_id={user_id}, title={title}, size={size}, duration={duration}, link={link}")


def get_upload_history(limit: int = 10) -> list:
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, title, size, duration, timestamp FROM uploads ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = c.fetchall()
    logger.info(f"Fetched last {limit} uploads.")
    return rows

# --- SLASH COMMANDS ---
@tree.command(name="whitelist", description="Manage the whitelist")
@app_commands.describe(action="add/remove/list", user="User to modify (only for add/remove)")
async def whitelist_cmd(interaction: discord.Interaction, action: str, user: discord.User = None):
    logger.info(f"Whitelist command by {interaction.user.id}: action={action}, target={getattr(user, 'id', None)}")
    if interaction.user.id != OWNER_ID:
        logger.warning(f"User {interaction.user.id} attempted whitelist management.")
        await interaction.response.send_message("Only the bot owner can manage the whitelist.", ephemeral=True)
        return

    action = action.lower()
    if action == "add":
        if user is None:
            await interaction.response.send_message("Please specify a user.", ephemeral=True)
            return
        add_to_whitelist(user.id)
        await interaction.response.send_message(f"User <@{user.id}> has been added to the whitelist.")

    elif action == "remove":
        if user is None:
            await interaction.response.send_message("Please specify a user.", ephemeral=True)
            return
        remove_from_whitelist(user.id)
        await interaction.response.send_message(f"User <@{user.id}> has been removed from the whitelist.")

    elif action == "list":
        ids = list_whitelisted_users()
        mentions = [f"<@{uid}>" for uid in ids]
        text = ", ".join(mentions) if mentions else "(empty)"
        await interaction.response.send_message(f"Current whitelist: {text}")

    else:
        await interaction.response.send_message("Action must be 'add', 'remove', or 'list'.", ephemeral=True)

# Register group
upload_group = app_commands.Group(name="upload", description="Manage uploads")
tree.add_command(upload_group)

@upload_group.command(name="link", description="Submit a media link to download")
@app_commands.describe(link="Media URL to download")
async def upload_link(interaction: discord.Interaction, link: str):
    logger.info(f"Upload link by {interaction.user.id}: {link}")
    if not is_whitelisted(interaction.user.id):
        logger.warning(f"Unauthorized upload_link by {interaction.user.id}")
        await interaction.response.send_message("You are not whitelisted.", ephemeral=True)
        return

    await interaction.response.send_message(f"🔗 Download started: {link}")
    try:
        title, size, duration = "Unknown", "? MB", "?"
        if "spotify.com" in link:
            logger.info("Spotify download via spotdl")
            proc = subprocess.run(["spotdl", link, "--output", MUSIC_DIR], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"spotdl exit code {proc.returncode}")
        else:
            logger.info("yt-dlp download")
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmpjson:
                proc = subprocess.run(["yt-dlp", "--dump-json", "-x", "--audio-format", "mp3", "-o", f"{MUSIC_DIR}/%(title)s.%(ext)s", link], stdout=tmpjson, stderr=subprocess.PIPE)
                logger.info(f"yt-dlp exit code {proc.returncode}")
                tmpjson.seek(0)
                try:
                    data = json.loads(tmpjson.read())
                    title = data.get("title", title)
                    duration = f"{round(data.get('duration',0)/60,2)} min"
                    size = f"{round((data.get('filesize') or 0)/1024/1024,2)} MB"
                    logger.info(f"Metadata: {title}, {duration}, {size}")
                except Exception as ex:
                    logger.error(f"JSON parse failed: {ex}")

        filepath = os.path.join(MUSIC_DIR, f"{title}.mp3")
        if title != "Unknown" and os.path.exists(filepath):
            logger.warning(f"Exists: {filepath}")
            await interaction.followup.send("⚠️ This file already exists.")
            return

        save_upload(interaction.user.id, link, title, size, duration)
        await interaction.followup.send("✅ Download finished.")
    except Exception as e:
        logger.exception(f"Download failed: {link}")
        await interaction.followup.send(f"❌ Download failed: {e}")

@upload_group.command(name="attachment", description="Upload an audio file (mp3, aac, opus)")
@app_commands.describe(file="Audio file to upload")
async def upload_attachment(interaction: discord.Interaction, file: discord.Attachment):
    logger.info(f"Upload attachment by {interaction.user.id}: {file.filename} ({file.size} bytes)")
    if not is_whitelisted(interaction.user.id):
        logger.warning(f"Unauthorized upload_attachment by {interaction.user.id}")
        await interaction.response.send_message("You are not whitelisted.", ephemeral=True)
        return

    if not any(file.filename.lower().endswith(ext) for ext in [".mp3", ".aac", ".opus"]):
        logger.warning(f"Unsupported file type: {file.filename}")
        await interaction.response.send_message("❌ Unsupported file type. Only MP3, AAC, OPUS allowed.", ephemeral=True)
        return

    dest = os.path.join(MUSIC_DIR, file.filename)
    await file.save(dest)
    size_str = f"{round(file.size/1024/1024,2)} MB"
    save_upload(interaction.user.id, file.url, file.filename, size_str, "?")
    logger.info(f"Saved file to {dest}")
    await interaction.response.send_message(f"✅ File uploaded: `{file.filename}`")

@upload_group.command(name="playlist", description="Download an entire playlist URL")
@app_commands.describe(link="Playlist URL to download")
async def upload_playlist(interaction: discord.Interaction, link: str):
    logger.info(f"Upload playlist by {interaction.user.id}: {link}")
    if not is_whitelisted(interaction.user.id):
        logger.warning(f"Unauthorized upload_playlist by {interaction.user.id}")
        await interaction.response.send_message("You are not whitelisted.", ephemeral=True)
        return

    await interaction.response.send_message(f"📥 Playlist download started: {link}")
    try:
        proc = subprocess.run(["yt-dlp", "-x", "--audio-format", "mp3", "--yes-playlist", "-o", f"{MUSIC_DIR}/%(playlist_title)s/%(title)s.%(ext)s", link], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info(f"yt-dlp playlist exit code {proc.returncode}")
        await interaction.followup.send("✅ Playlist download finished.")
    except Exception as e:
        logger.exception(f"Playlist download failed: {link}")
        await interaction.followup.send(f"❌ Playlist download failed: {e}")

@upload_group.command(name="list", description="Show latest uploads")
@app_commands.describe(limit="Number of items to show (max 20)")
async def upload_list(interaction: discord.Interaction, limit: int = 10):
    logger.info(f"Upload list by {interaction.user.id}, limit={limit}")
    if not is_whitelisted(interaction.user.id):
        logger.warning(f"Unauthorized upload_list by {interaction.user.id}")
        await interaction.response.send_message("You are not whitelisted.", ephemeral=True)
        return

    limit = min(limit, 20)
    rows = get_upload_history(limit)
    embed = discord.Embed(title="Latest Uploads", color=0x00ff00)
    for user_id, title, size,	duration, ts in rows:
        time = datetime.datetime.fromisoformat(ts).strftime('%Y-%m-%d %H:%M')
        embed.add_field(
            name=f"{title}",
            value=f"From: <@{user_id}> | Size: {size} | Duration: {duration} | {time}",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

# --- EVENTS & RUN ---
@client.event
async def on_ready():
    init_db()
    if not getattr(client, 'commands_synced', False):
        await tree.sync()
        client.commands_synced = True
    logger.info(f"Bot ready as {client.user}")

client.run(TOKEN)
