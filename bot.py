import discord
import subprocess
import os

TOKEN = os.getenv("DISCORD_TOKEN")
MUSIC_DIR = "/music"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Bot eingeloggt als {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip()

    if content.startswith("https://"):
        await message.channel.send(f"🔗 Link erkannt, starte Download: {content}")

        if "spotify.com" in content:
            cmd = ["spotdl", content, "--output", MUSIC_DIR]
        else:
            cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "-o", f"{MUSIC_DIR}/%(title)s.%(ext)s", content]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode == 0:
            await message.channel.send("✅ Download abgeschlossen.")
        else:
            await message.channel.send("❌ Fehler beim Download.")
            print(result.stderr.decode())

    elif message.attachments:
        for att in message.attachments:
            filename = att.filename.lower()
            if filename.endswith((".mp3", ".aac", ".opus")):
                save_path = os.path.join(MUSIC_DIR, att.filename)
                await att.save(save_path)
                await message.channel.send("✅ Datei gespeichert.")
            else:
                await message.channel.send("⚠️ Nur mp3, opus oder aac erlaubt.")

client.run(TOKEN)
