import discord
from discord.ext import commands
from discord.commands import Option, slash_command
from asyncio import Queue, run_coroutine_threadsafe
import yt_dlp
import re
import asyncio

intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

music_queues = {}
song_played_positions = {}  # Dictionary to track the position of the current song for each guild
playlist_positions = {}     # Tracks song positions for each guild
playlist_messages = {}      # Dictionary to track the playlist messages for each guild

thea_playlist = [
    "https://youtu.be/T17OozgVt5s",
    "https://youtu.be/CWbcmTMNKdk",
    "https://youtu.be/kBSCSWkWrYw",
    "https://youtu.be/HAc57Xd-m6Q",
    "https://youtu.be/HhNw464QKIE",
    "https://youtu.be/urLYT52vAUU",
    "https://youtu.be/LZ4MAVh53OA",
    "https://youtu.be/gDMkiOM7t34",
    "https://youtu.be/siXX5rh-wEI",
    "https://youtu.be/nutwTeKKoOk",
    "https://youtu.be/kpI7U_QO7Ck",
    "https://youtu.be/fc6PgIMclY8",
    "https://youtu.be/uEQ1rpvTGmA",
    "https://youtu.be/5zWUCdz4_wc",
    "https://youtu.be/W6n14deCAxU",
    "https://youtu.be/xtcEuBYmB0w",
    "https://youtu.be/-5kPBJH_jQc",
    "https://youtu.be/KZXIAdqX20g",
    "https://youtu.be/tw6IHuG359s",
    #EGO de sunyel ft théa introuvable
    "https://youtu.be/U6didLpHRig",
    "https://youtu.be/66wP8Q_PA0Q",
    "https://youtu.be/rl4-vkvfR0A",
    "https://youtu.be/aSHzhTLR7Cs",
    #Dopamine de théa ft sunyel introuvable
    "https://youtu.be/zLRfkoMQAUc",
    "https://youtu.be/XjX5-Yt1VME",
    # Semer la ville de théa ft ash léa introuvable
    "https://youtu.be/UQ7K8cW3BLs"
    #Lacunaire de théa ft mrs yéyé introuvable / https://youtu.be/oQahU1COcsI
    # excès et déni de théa introuvable / https://youtu.be/5wX0CHQPdz8
    # De nos p'tits bras introuvable 

]
guild_playlists = {}


@client.slash_command(name="slashping", description="Test command")
async def slashping(ctx: discord.Interaction):
    await ctx.response.send_message(f"Pong! ({round(client.latency * 1000, 2)}) ms")

@client.command(pass_context=True)
async def ping(ctx):
    await ctx.send(f"Pong! ({round(client.latency * 1000, 2)}) ms")

# Function to check if a string is a URL
def is_url(string):
    regex = re.compile(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be|soundcloud\.com)/.+$')
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
    seconds = round(seconds)
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f'{hours:02}:{mins:02}:{secs:02}'
    else:
        return f'{mins:02}:{secs:02}'


def get_audio_info(url):
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

    # Increment the current song played counter for this guild
    song_played_positions[guild_id] += 1

    # Get the next song URL from the queue
    url = await music_queues[guild_id].get()
    stream_url, title, thumbnail, duration = get_audio_info(url)

    vc.play(discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop).result())

    duration_str = format_duration(duration)

    # Retrieve and delete the "added to playlist" message for the current song
    if song_played_positions[guild_id] in playlist_messages[guild_id]:
        added_msg = playlist_messages[guild_id].pop(song_played_positions[guild_id])
        await added_msg.delete()

    embed = discord.Embed(
        title=f"En train de jouer : {title} !",
        url=url,
        description=f"Durée : {duration_str}\nMusique N°{song_played_positions[guild_id]}",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=thumbnail)

    # Send a new message instead of replying to the original interaction
    await ctx.channel.send(embed=embed)


@client.slash_command(name="play", description="Joue une musique")
async def play(ctx: discord.Interaction, query: str):
    await ctx.response.defer()
    guild_id = ctx.guild.id

    # Initialize the queue, song position counter, and playlist message store if not already set
    if guild_id not in music_queues:
        music_queues[guild_id] = Queue()
        playlist_positions[guild_id] = 0
        song_played_positions[guild_id] = 0
        playlist_messages[guild_id] = {}

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

    stream_url, title, thumbnail, duration = get_audio_info(url)
    duration_str = format_duration(duration)
    
    # Calculate the next song position in the playlist
    playlist_positions[guild_id] += 1

    embed = discord.Embed(
        title=f"{title} a été ajouté à la playlist !",
        url=url,
        description=f"Durée : {duration_str}\nMusique N°{playlist_positions[guild_id]}",
        color=discord.Color.orange()
    )
    embed.set_thumbnail(url=thumbnail)
    added_msg = await ctx.respond(embed=embed)

    # Store the message object in the dictionary
    playlist_messages[guild_id][playlist_positions[guild_id]] = added_msg

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

async def play_from_playlist(ctx: discord.Interaction):
    guild_id = ctx.guild.id
    vc = ctx.guild.voice_client

    if guild_id not in guild_playlists or guild_playlists[guild_id] >= len(thea_playlist):
        # Playlist is finished or not started yet, reset position and leave
        guild_playlists[guild_id] = 0
        if vc and vc.is_connected():
            await vc.disconnect()
        return

    # Get the current song from the playlist
    url = thea_playlist[guild_playlists[guild_id]]
    stream_url, title, thumbnail, duration = get_audio_info(url)

    vc.play(discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_from_playlist(ctx), client.loop).result())

    duration_str = format_duration(duration)

    embed = discord.Embed(
        title=f"En train de jouer : {title} !",
        url=url,
        description=f"Durée : {duration_str}\nMusique N°{guild_playlists[guild_id] + 1}",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=thumbnail)

    await ctx.channel.send(embed=embed)

    # Move to the next song in the playlist
    guild_playlists[guild_id] += 1

@client.slash_command(name="théa", description="!NE PAS UTILISER / PAS FINI! Joue toutes les musiques de théa")
async def théa(ctx: discord.Interaction):
    await ctx.response.defer()
    guild_id = ctx.guild.id

    # Initialize the playlist position for the guild
    if guild_id not in guild_playlists:
        guild_playlists[guild_id] = 0

    # Check if the user is in a voice channel
    if not ctx.author.voice:
        await ctx.respond("Tu n'es pas dans un salon vocal, rejoin une voc et relance la commande !")
        return

    voice_channel = ctx.author.voice.channel
    vc = ctx.voice_client

    if vc is None:
        vc = await voice_channel.connect()

    # Start playing from the playlist
    if not vc.is_playing():
        await play_from_playlist(ctx)

@client.slash_command(name="leave", description="Quitte la voc")
async def leave(ctx: discord.Interaction):
    guild_id = ctx.guild.id
    if ctx.voice_client:
        guild_playlists[guild_id] = 0
        await ctx.guild.voice_client.disconnect()
        ack_msg = await ctx.response.send_message("Déconnexion en cours...", delete_after=0)
    else:
        await ctx.respond("Je ne peux pas quitter la voc, puisque je ne suis pas dedans !")

@client.event
async def on_voice_state_update(member, before, after):
    # Check if the bot is disconnected from the voice channel
    if member == client.user and before.channel is not None and after.channel is None:
        guild_id = before.channel.guild.id
        # Reset counters and clear messages
        playlist_positions[guild_id] = 0
        song_played_positions[guild_id] = 0
        playlist_messages[guild_id] = {}  # Clear playlist messages

        channel = before.channel.guild.system_channel  # Or specify the channel to send the message to
        if channel:
            await channel.send("J'ai été déconnecté de la voc !")


@client.event
async def on_ready():
    print("Théa prêt")

f = open("token", "r")
token = f.readlines()

client.run(token[0])
