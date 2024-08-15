import discord
from discord.ext import commands
from discord.commands import Option, slash_command
from asyncio import Queue, run_coroutine_threadsafe, get_running_loop
import yt_dlp
import re
import asyncio

intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

music_queues = {}
song_positions = {}  # Dictionary to track the position of the current song for each guild
playlist_pos = 0

@client.slash_command(name="slashping", description="Test command")
async def slashping(ctx: discord.Interaction):
    await ctx.response.send_message("Pong!")

@client.command(pass_context=True)
async def ping(ctx):
    await ctx.send("Pong!")

# Function to check if a string is a URL
def is_url(string):
    regex = re.compile(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$')
    return re.match(regex, string) is not None

# Function to search YouTube and get the first result
def search_youtube(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'extract_flat': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        search_result = ydl.extract_info(f"ytsearch:{query}", download=False)
        if search_result and 'entries' in search_result and len(search_result['entries']) > 0:
            return f"https://www.youtube.com/watch?v={search_result['entries'][0]['id']}"
        else:
            return None

def format_duration(seconds):
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f'{hours:02}:{mins:02}:{secs:02}'
    else:
        return f'{mins:02}:{secs:02}'

def get_youtube_audio_info(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        duration = info.get('duration', 0)
        return info['url'], info['title'], info['thumbnail'], duration

async def play_next(ctx: discord.Interaction, triggered_by_next=False):
    guild_id = ctx.guild.id
    vc = ctx.guild.voice_client

    if guild_id not in music_queues or music_queues[guild_id].empty():
        # Queue is empty, leave the voice channel
        if vc and vc.is_connected():
            await vc.disconnect()
        # Only send the message if it was triggered by the /next command
        if triggered_by_next:
            await ctx.followup.send("C'était la dernière musique, il n'y en a plus dans la liste !")
        return

    # Increment the current song counter for this guild
    song_positions[guild_id] += 1

    # Get the next song URL from the queue
    url = await music_queues[guild_id].get()
    stream_url, title, thumbnail, duration = get_youtube_audio_info(url)

    vc.play(discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop).result())

    duration_str = format_duration(duration)
    embed = discord.Embed(
        title=f"En train de jouer : {title} !",
        url=url,
        description=f"Durée : {duration_str}\nMusique N°{song_positions[guild_id]}",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=thumbnail)
    await ctx.followup.send(embed=embed)

@client.slash_command(name="play", description="Joue une musique")
async def play(ctx: discord.Interaction, query: str):
    global playlist_pos
    await ctx.response.defer()
    guild_id = ctx.guild.id

    # Initialize the queue and song position counter if not already set
    if guild_id not in music_queues:
        music_queues[guild_id] = Queue()
        song_positions[guild_id] = 0

    # Check if the user is in a voice channel
    if not ctx.author.voice:
        await ctx.respond("Tu n'es pas dans un salon vocal, rejoin une voc et relance la commande !")
        return

    # Determine if the input is a URL or a search query
    if not is_url(query):
        url = search_youtube(query)
        if url is None:
            await ctx.respond("Rien trouvé ¯\\_(ツ)_/¯")
            return
    else:
        url = query

    stream_url, title, thumbnail, duration = get_youtube_audio_info(url)
    duration_str = format_duration(duration)
    
    # Calculate the next song position
    playlist_pos +=1

    embed = discord.Embed(
        title=f"{title} a été ajouté à la playlist !",
        url=url,
        description=f"Durée : {duration_str}\nMusique N°{playlist_pos}",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=thumbnail)
    await ctx.respond(embed=embed)

    await music_queues[guild_id].put(url)

    voice_channel = ctx.author.voice.channel
    vc = ctx.voice_client

    if vc is None:
        vc = await voice_channel.connect()

    if not vc.is_playing():
        await play_next(ctx)


@client.slash_command(name="next", description="Joue la prochaine musique de la playlist")
async def next(ctx: discord.Interaction):
    await ctx.response.defer()
    vc = ctx.voice_client
    guild_id = ctx.guild.id

    if guild_id in music_queues:
        # Check if the queue has more songs left
        if not music_queues[guild_id].empty():
            if vc and vc.is_playing():
                vc.stop()  # Stop the current song and trigger play_next
            else:
                await play_next(ctx, triggered_by_next=True)
        else:
            await ctx.respond("C'était la dernière musique, il n'y en a plus dans la liste !")
    else:
        await ctx.respond("Il n'y a aucune musique en attente dans la liste !")

@client.slash_command(name="leave", description="Quitte la voc")
async def leave(ctx:discord.Interaction):
    if ctx.voice_client:
        await ctx.guild.voice_client.disconnect()
        await ctx.respond("J'ai fini !")
    else:
        await ctx.respond("Je ne peux pas quitter la voc, puisque je ne suis pas dedans !")

@client.event
async def on_ready():
    print("Théa prêt")

f = open("token", "r")
token = f.readlines()

client.run(token[0])
