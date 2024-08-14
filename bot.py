import discord
from discord.ext import commands
from discord.commands import Option, slash_command
from asyncio import Queue, run_coroutine_threadsafe, get_running_loop
import yt_dlp
import re
import asyncio

intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix = "!", intents=intents)
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn'}

music_queues = {}

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

def get_youtube_audio_info(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info['url'], info['title'], info['thumbnail']

async def play_next(ctx):
    guild_id = ctx.guild.id
    
    # Check if the queue exists and if it's empty
    url = await music_queues[guild_id].get()
    stream_url, title, thumbnail = get_youtube_audio_info(url)

    vc = ctx.voice_client

    vc.play(discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop).result())
    embed = discord.Embed(
        title=f"En train de jouer : {title} !",
        url=url,
        description="En train de jouer cette musique.",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=thumbnail)
    await ctx.respond(embed=embed)
        #await ctx.send(f"En train de jouer : [{title}]({url})")


#@client.command(pass_context=True)
@client.slash_command(name="play", description="Joue une musique")
async def play(ctx:discord.Interaction, query: str):
    # Check if the user is in a voice channel
    if not ctx.author.voice:
        await ctx.respond("Tu n'es pas dans un salon vocal, rejoin une voc et relance la commande !")
        return

    # Determine if the input is a URL or a search query
    if not is_url(query):
        url = search_youtube(query)
        if url is None:
            await ctx.respond("Rien trouvé ¯\_(ツ)_/¯")
            return
    else:
        url = query

    stream_url, title, thumbnail = get_youtube_audio_info(url)

    embed = discord.Embed(
        title=f"{title} a été ajouté a la playliste !",
        url=url,
        description="Cette musique a été ajouté a la playliste.",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=thumbnail)
    await ctx.respond(embed=embed)

    guild_id = ctx.guild.id

    if guild_id not in music_queues:
        music_queues[guild_id] = Queue()

    await music_queues[guild_id].put(url)

    voice_channel = ctx.author.voice.channel
    vc = ctx.voice_client

    if vc is None:
        vc = await voice_channel.connect()

    if not vc.is_playing():
        await play_next(ctx)

#@client.command(pass_context=True)
@client.slash_command(name="next", description="Joue la prochaine musique de la playliste")
async def next(ctx:discord.Interaction):
    vc = ctx.voice_client
    guild_id = ctx.guild.id
    if guild_id in music_queues and music_queues[guild_id].empty():
        await ctx.respond("C'était la dernière musique, il n'y en a plus dans la liste !")
    else:
        # Continue playing the next song in the queue
        if vc and vc.is_playing():
            vc.stop()
        await play_next(ctx)

#@client.command(pass_context=True)
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