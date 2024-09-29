import discord
from discord.ext import commands
from discord.commands import Option, slash_command
from discord import ButtonStyle
from asyncio import Queue, run_coroutine_threadsafe
import yt_dlp
import re
import asyncio
import os
import subprocess
import random

intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix="!", intents=intents)
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

music_queues = {}
song_played_positions = {}  # Dictionary to track the position of the current song for each guild
playlist_positions = {}     # Tracks song positions for each guild
playlist_messages = {}      # Dictionary to track the playlist messages for each guild

thea_playlist = [
    "https://youtu.be/T17OozgVt5s", # PTSMR
    "https://youtu.be/CWbcmTMNKdk", # TEEN MOVIE
    "https://youtu.be/kBSCSWkWrYw", # JUSTE AMIS
    "https://youtu.be/HAc57Xd-m6Q", # ENFANT D'LA RAVE
    "https://youtu.be/HhNw464QKIE", # ANXIOLYTIQUES
    "https://youtu.be/urLYT52vAUU", # HANNAH MONTANA
    "https://youtu.be/LZ4MAVh53OA", # Bal de chair
    "https://youtu.be/gDMkiOM7t34", # AAAAAAH
    "https://youtu.be/siXX5rh-wEI", # A la mort
    "https://youtu.be/nutwTeKKoOk", # Derniers mots
    "https://youtu.be/kpI7U_QO7Ck", # Entropie
    "https://youtu.be/fc6PgIMclY8", # Sous la lune
    "https://youtu.be/uEQ1rpvTGmA", # Ca ira
    "https://youtu.be/5zWUCdz4_wc", # De salem et d'ailleur
    "https://youtu.be/W6n14deCAxU", # Grisaille
    "https://youtu.be/xtcEuBYmB0w", # Quoi de neuf les voyous
    "https://youtu.be/-5kPBJH_jQc", # Echo
    "https://youtu.be/KZXIAdqX20g", # Enfant Doué.e
    "https://youtu.be/tw6IHuG359s", # Guillotine
    #EGO de sunyel ft théa introuvable
    "https://youtu.be/U6didLpHRig", # Plume
    "https://youtu.be/66wP8Q_PA0Q", # Pourtant
    "https://youtu.be/rl4-vkvfR0A", # Ennui
    "https://youtu.be/aSHzhTLR7Cs", # Flemme
    #Dopamine de théa ft sunyel introuvable
    "https://youtu.be/zLRfkoMQAUc", # Plus rien n'existe
    "https://youtu.be/XjX5-Yt1VME", # Solitaires (ft sunyel la pedo)
    # Semer la ville de théa ft ash léa introuvable
    "https://youtu.be/UQ7K8cW3BLs", # Et la haine ? 
    "https://youtu.be/JBxNWTS9_-0", # Lacunaire
    "https://youtu.be/5wX0CHQPdz8" # Excès et déni
    # De nos p'tits bras introuvable 

]
guild_playlists = {}

class MusicControlView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=None)  # No timeout for buttons
        self.ctx = ctx 
        self.paused = False  # Track whether music is paused or not

    # Pause/Resume button
    @discord.ui.button(label="⏸ Pause", style=ButtonStyle.primary, custom_id="pause")
    async def toggle_pause(self, button: discord.ui.Button, interaction: discord.Interaction):
        vc = self.ctx.guild.voice_client
        if vc is None or not vc.is_connected():
            await interaction.response.send_message("Je ne suis pas connecté à un salon vocal.")
            return

        if self.paused:
            vc.resume()
            self.paused = False
            button.label = "⏸ Pause" 
            button.style = ButtonStyle.primary
            await interaction.response.edit_message(view=self)
        else:
            vc.pause()
            self.paused = True
            button.label = "▶ Resume"
            button.style = ButtonStyle.success
            await interaction.response.edit_message(view=self)

    # Skip button
    @discord.ui.button(label="⏭ Skip", style=ButtonStyle.primary, custom_id="skip")
    async def skip(self, button: discord.ui.Button, interaction: discord.Interaction):
        vc = self.ctx.guild.voice_client
        if vc is None or not vc.is_connected():
            await interaction.response.send_message("Je ne suis pas connecté à un salon vocal.")
            return
        #if vc.is_playing():
        vc.stop()
        await interaction.response.send_message("Musique passée !")

    # Stop button
    @discord.ui.button(label="⏹ Stop", style=ButtonStyle.danger, custom_id="stop")
    async def stop(self, button: discord.ui.Button, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        vc = self.ctx.guild.voice_client

        if vc is None or not vc.is_connected():
            await interaction.response.send_message("Je ne suis pas connecté à un salon vocal.")
            return

        if vc.is_playing():
            vc.stop()
            await interaction.response.send_message("J'ai quitté la voc !.")
        if vc.is_connected():
            await vc.disconnect()
            await interaction.response.send_message("J'ai quitté la voc !.")




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

# Gets the duration of a local audio file using ffprobe
def get_file_duration(filepath: str) -> str:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        duration = float(result.stdout)
        return format_duration(duration)
    except Exception as e:
        print(e)
        return "Inconnue"  # Return "Unknown" if duration can't be determined

async def play_next(ctx: discord.Interaction):
    guild_id = ctx.guild.id
    vc = ctx.guild.voice_client

    if guild_id not in music_queues or music_queues[guild_id].empty():
        # No more songs in the queue, reset and disconnect
        playlist_positions[guild_id] = 0
        song_played_positions[guild_id] = 0
        await vc.disconnect()
        return

    url = await music_queues[guild_id].get()

    if url.startswith("http") and "youtube" in url:
        stream_url, title, thumbnail, duration = get_audio_info(url)
        duration_str = format_duration(duration)
        embed = discord.Embed(
            title=f"En train de jouer : {title} !",
            url=url,
            description=f"Durée : {duration_str}\nMusique N°{song_played_positions[guild_id] + 1}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=thumbnail)
    else:
        # Local file attachment
        stream_url = url 
        title = os.path.basename(url).split("?")[0] 
        duration_str = get_file_duration(url)
        embed = discord.Embed(
            title=f"En train de jouer : {title} !",
            description=f"Durée : {duration_str}\nMusique N°{song_played_positions[guild_id] + 1}",
            url=url,
            color=discord.Color.blurple()
        )
    view = MusicControlView(ctx)
    

    await ctx.channel.send(embed=embed, view=view)

    vc.play(discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop).result())

    song_played_positions[guild_id] += 1



@client.slash_command(name="play", description="Joue une musique")
async def play(ctx: discord.Interaction, query: str = None, attachment: discord.Attachment = None):
    await ctx.response.defer()
    guild_id = ctx.guild.id

    if guild_id not in music_queues:
        music_queues[guild_id] = Queue()
        playlist_positions[guild_id] = 0
        song_played_positions[guild_id] = 0
        playlist_messages[guild_id] = {}

    if not ctx.author.voice:
        await ctx.respond("Tu n'es pas dans un salon vocal, rejoins un voc et relance la commande !")
        return

    voice_channel = ctx.author.voice.channel
    vc = ctx.voice_client

    if attachment is not None:
        url = attachment.url
        title = attachment.filename
        thumbnail = None
        duration = get_file_duration(url)
        stream_url = url
        duration_str = duration

    elif query is not None:
        if not is_url(query):
            url = search_youtube(query)
            if url is None:
                await ctx.respond("Rien trouvé ¯\\_(ツ)_/¯")
                return
        else:
            url = query

        stream_url, title, thumbnail, duration = get_audio_info(url)
        duration_str = format_duration(duration)
    else:
        await ctx.respond("Il faut me donner un lien, une recherche ou un fichier.")
        return

    # If this is the first song, start playing it immediately and don't add it to the playlist
    if not vc or not vc.is_playing():
        if vc is None:
            vc = await voice_channel.connect()
    
        embed = discord.Embed(
            title=f"En train de jouer : {title} !",
            url=url,
            description=f"Durée : {duration_str}\nMusique N°1",
            color=discord.Color.blurple()
        )
        view = MusicControlView(ctx)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        await ctx.channel.send(embed=embed, view=view)

        vc.play(discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS),
                after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop).result())
        song_played_positions[guild_id] += 1

    else:
        # Increment the playlist position only when adding to the queue
        playlist_positions[guild_id] += 1
        await music_queues[guild_id].put(url)

        embed = discord.Embed(
            title=f"{title} a été ajouté à la playlist !",
            url=url,
            description=f"Durée : {duration_str}\nMusique N°{playlist_positions[guild_id] + 1}",
            color=discord.Color.orange()
        )
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        added_msg = await ctx.channel.send(embed=embed)

        playlist_messages[guild_id][playlist_positions[guild_id]] = added_msg


@client.slash_command(name="next", description="Passe à la musique suivante")
async def next(ctx: discord.Interaction):
    guild_id = ctx.guild.id
    vc = ctx.guild.voice_client

    if guild_id not in guild_playlists:
        guild_playlists[guild_id] = 0

    if not vc or not vc.is_connected():
        await ctx.respond("Je ne suis pas connecté à un salon vocal.")
        return

    if not vc.is_playing():
        await ctx.respond("Aucune musique n'est en train de jouer.")
        return

    if guild_playlists[guild_id] >= len(thea_playlist):
        await ctx.respond("Il n'y a plus de musiques dans la playlist.")
        return

    vc.stop()
    await ctx.respond("Passage à la musique suivante...", delete_after=0)


async def play_from_thea(ctx: discord.Interaction):
    guild_id = ctx.guild.id
    vc = ctx.guild.voice_client

    if vc is None or not vc.is_connected():
        guild_playlists[guild_id] = 0
        return

    if guild_id not in guild_playlists or guild_playlists[guild_id] >= len(thea_playlist):
        guild_playlists[guild_id] = 0
        await vc.disconnect()
        return

    url = thea_playlist[guild_playlists[guild_id]]
    stream_url, title, thumbnail, duration = get_audio_info(url)

    vc.play(discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS),
            after=lambda e: asyncio.run_coroutine_threadsafe(play_from_thea(ctx), client.loop).result())

    duration_str = format_duration(duration)

    embed = discord.Embed(
        title=f"En train de jouer : {title} !",
        url=url,
        description=f"Durée : {duration_str}\nMusique N°{guild_playlists[guild_id] + 1}",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=thumbnail)
    view = MusicControlView(ctx)

    await ctx.channel.send(embed=embed, view=view)

    # Move to the next song in the playlist
    guild_playlists[guild_id] += 1

@client.slash_command(name="théa", description="Joue toutes les musiques de Théa")
async def théa(ctx: discord.Interaction):
    await ctx.response.defer()
    guild_id = ctx.guild.id

    if guild_id not in guild_playlists:
        guild_playlists[guild_id] = 0

    random.shuffle(thea_playlist)

    if not ctx.author.voice:
        await ctx.respond("Tu n'es pas dans un salon vocal, rejoins une voc et relance la commande !")
        return

    voice_channel = ctx.author.voice.channel
    vc = ctx.voice_client

    embed = discord.Embed(
        title=f"Je vais jouer toutes les musiques de Théa en mode aléatoire !",
        description="Liste des musiques disponibles :\n\n PTSMR\nTEEN MOVIE\nJUSTE AMIS\nENFANTS D'LA RAVE\n ANXIOLYTIQUES\nHANNAH MONTANA\nBal de chair\nAAAAAAAH\nA la mort\n Derniers mots\nEntropie\nSous la lune\nCa ira\nDe salem et d'ailleur\nGrisaille\nQuoi de neuf les voyous\nEcho\nEnfant Doué.e\nGuillotine\nPlume\nPourtant\nEnnui\nFlemme\nPlus rien n'existe\nSolitaires (ft sunyel la pedo)\nEt la haine?\nLacunaire\nExcès et Déni",
        color=discord.Color.from_rgb(235, 76, 200)
    )
    await ctx.respond(embed=embed)

    if vc is None:
        vc = await voice_channel.connect()

    if not vc.is_playing():
        await play_from_thea(ctx)


@client.slash_command(name="leave", description="Quitte la voc")
async def leave(ctx: discord.Interaction):
    guild_id = ctx.guild.id
    if ctx.voice_client:
        guild_playlists[guild_id] = 0
        await ctx.guild.voice_client.disconnect()
        await ctx.response.send_message("Déconnexion en cours...", delete_after=0)
    else:
        await ctx.respond("Je ne peux pas quitter la voc, puisque je ne suis pas dedans !")

@client.event
async def on_voice_state_update(member, before, after):
    if member == client.user and before.channel is not None and after.channel is None:
        guild_id = before.channel.guild.id
        playlist_positions[guild_id] = 0
        song_played_positions[guild_id] = 0
        playlist_messages[guild_id] = {}

        #for your own use, prescise the id you your channel where you want to sentd this message
        # or send it in the system channel :
        #channel = before.channel.guild.system_channel
        channel_id = 1132378677175394378
        channel = before.channel.guild.get_channel(channel_id)
        if channel:
            await channel.send("J'ai été déconnecté de la voc !")


@client.event
async def on_ready():
    print("Théa prêt")

f = open("token", "r")
token = f.readlines()

client.run(token[0])
