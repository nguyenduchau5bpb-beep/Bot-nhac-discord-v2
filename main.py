import os
import asyncio
from flask import Flask
from threading import Thread
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp

# --- WEB SERVER FLASK GIỮ PORT CỦA RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot nhạc Discord 24/7 đang hoạt động mượt mà!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- CẤU HÌNH BOT DISCORD ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch',
}
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

queues = {}

@bot.event
async def on_ready():
    print(f"🤖 Bot online dưới tên: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Đã đồng bộ {len(synced)} lệnh Slash!")
    except Exception as e:
        print(f"❌ Lỗi sync lệnh: {e}")

# --- SLASH COMMANDS ---
@bot.tree.command(name="play", description="Tìm và phát nhạc từ YouTube")
@app_commands.describe(query="Tên bài hát hoặc URL")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    
    if not interaction.user.voice:
        return await interaction.followup.send("❌ Bạn phải vào phòng voice trước!")

    voice_channel = interaction.user.voice.channel
    guild_id = interaction.guild_id

    voice_client = interaction.guild.voice_client
    if not voice_client:
        voice_client = await voice_channel.connect()

    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ytdl:
        info = ytdl.extract_info(f"ytsearch:{query}", download=False)
        if 'entries' in info and len(info['entries']) > 0:
            info = info['entries'][0]
        else:
            return await interaction.followup.send("❌ Không tìm thấy bài hát!")

    song = {'title': info['title'], 'url': info['url']}

    if guild_id not in queues:
        queues[guild_id] = []
    queues[guild_id].append(song)

    if voice_client.is_playing() or voice_client.is_paused():
        await interaction.followup.send(f"✅ Đã thêm vào hàng chờ: **{song['title']}**")
    else:
        play_next(interaction, guild_id, voice_client)
        await interaction.followup.send(f"🎶 Đang phát: **{song['title']}**")

def play_next(interaction, guild_id, voice_client):
    if queues.get(guild_id) and len(queues[guild_id]) > 0:
        song = queues[guild_id].pop(0)
        source = discord.FFmpegPCMAudio(song['url'], **FFMPEG_OPTIONS)
        voice_client.play(source, after=lambda e: play_next(interaction, guild_id, voice_client))
    else:
        asyncio.run_coroutine_threadsafe(voice_client.disconnect(), bot.loop)

@bot.tree.command(name="skip", description="Bỏ qua bài hiện tại")
async def skip(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message("⏭️ Đã bỏ qua bài hát!")
    else:
        await interaction.response.send_message("❌ Không có bài hát nào đang phát!", ephemeral=True)

@bot.tree.command(name="stop", description="Dừng nhạc và dọn hàng chờ")
async def stop(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    voice_client = interaction.guild.voice_client
    if guild_id in queues:
        queues[guild_id] = []
    if voice_client:
        await voice_client.disconnect()
    await interaction.response.send_message("⏹️ Đã dừng phát nhạc và rời phòng!")

if __name__ == "__main__":
    keep_alive()
    bot.run(os.environ.get("DISCORD_TOKEN"))
