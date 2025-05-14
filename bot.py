# bot.py
import discord
from discord import app_commands
import os
import subprocess
import sqlite3
import datetime
import tempfile
import json

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("DISCORD_OWNER_ID", "0"))
MUSIC_DIR = "/music"
DB_FILE = "botdata.db"

intents = discord.Intents.default()
intents.message_content = True
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
        # Auto-whitelist the owner
        c.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (OWNER_ID,))
        conn.commit()

def is_whitelisted(user_id: int) -> bool:
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (user_id,))
        return c.fetchone() is not None

def add_to_whitelist(user_id: int):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (user_id,))
        conn.commit()

def remove_from_whitelist(user_id: int):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM whitelist WHERE user_id = ?", (user_id,))
        conn.commit()

def list_whitelisted_users():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM whitelist")
        return [str(row[0]) for row in c.fetchall()]

def save_upload(user_id: int, link: str, title: str, size: str, duration: str):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO uploads (user_id, link, title, size, duration, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, link, title, size, duration, datetime.datetime.now().isoformat()))
        conn.commit()

def get_upload_history():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, title, link, size, duration FROM uploads ORDER BY id DESC LIMIT 20")
        return c.fetchall()

# --- SLASH COMMANDS ---
@tree.command(name="whitelist", description="Manage the whitelist")
@app_commands.describe(action="add/remove/list", user="User to modify (only for add/remove)")
async def whitelist_cmd(interaction: discord.Interaction, action: str, user: discord.User = None):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("You are not authorized to manage the whitelist.", ephemeral=True)
        return

    if action == "list":
        users = list_whitelisted_users()
        msg = "Whitelisted users:\n" + "\n".join(users) if users else "Whitelist is empty."
        await interaction.response.send_message(msg, ephemeral=True)
    elif action in ["add", "remove"] and user:
        if action == "add":
            add_to_whitelist(user.id)
            try:
                await user.send("You've been granted access to the Navidrome music bot.")
            except:
                pass
            await interaction.response.send_message(f"✅ {user.mention} added to whitelist.", ephemeral=True)
        else:
            remove_from_whitelist(user.id)
            await interaction.response.send_message(f"❌ {user.mention} removed from whitelist.", ephemeral=True)
    else:
        await interaction.response.send_message("Invalid usage.", ephemeral=True)

@tree.command(name="upload", description="Download and add a song from a media link")
@app_commands.describe(link="Media URL to download")
async def upload_cmd(interaction: discord.Interaction, link: str):
    if not is_whitelisted(interaction.user.id):
        await interaction.response.send_message("You are not whitelisted. Contact the instance owner.", ephemeral=True)
        return

    await interaction.response.send_message(f"🔗 Download started: {link}")

    try:
        title = "Unknown Title"
        size = "? MB"
        duration = "?"

        if "spotify.com" in link:
            cmd = ["spotdl", link, "--output", MUSIC_DIR]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmpjson:
                cmd = ["yt-dlp", "--dump-json", "-x", "--audio-format", "mp3",
                       "-o", f"{MUSIC_DIR}/%(title)s.%(ext)s", link]
                proc = subprocess.run(cmd, stdout=tmpjson, stderr=subprocess.PIPE)
                tmpjson.seek(0)
                try:
                    data = json.loads(tmpjson.read())
                    title = data.get("title", "Unknown Title")
                    duration = f"{round(data.get('duration', 0)/60, 2)} min"
                    size = f"{round(data.get('filesize', 0)/1024/1024, 2)} MB"
                except Exception:
                    pass

        # Check for existing file
        if title != "Unknown Title":
            filepath = os.path.join(MUSIC_DIR, f"{title}.mp3")
            if os.path.exists(filepath):
                await interaction.followup.send("⚠️ This file already exists in the library.")
                return

        save_upload(interaction.user.id, link, title, size, duration)
        await interaction.followup.send("✅ Download finished.")
    except Exception as e:
        await interaction.followup.send(f"❌ Download failed: {e}")

@tree.command(name="upload_list", description="Show the latest uploads")
async def upload_list(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Not authorized.", ephemeral=True)
        return

    entries = get_upload_history()
    if not entries:
        await interaction.response.send_message("No uploads found.", ephemeral=True)
        return

    message = ""
    for row in entries:
        message += f"<@{row[0]}> : {row[4]}\n{row[2] or row[1]}\n{row[3]}\n\n"

    await interaction.response.send_message(f"```{message}```", ephemeral=True)

# --- EVENTS ---
@client.event
async def on_ready():
    init_db()
    if not getattr(client, 'commands_synced', False):
        await tree.sync()
        client.commands_synced = True
    print(f"✅ Bot logged in as {client.user}")

client.run(TOKEN)
