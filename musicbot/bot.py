import os
import sys
import time
import shlex
import shutil
import random
import inspect
import logging
import asyncio
import pathlib
import traceback
import watchtower
import weakref

import copy as copy

import aiohttp
import discord
import colorlog

from io import BytesIO, StringIO
from functools import wraps
from textwrap import dedent
from datetime import timedelta, datetime
from collections import defaultdict

from discord.enums import ChannelType
from discord.ext.commands.bot import _get_variable
from discord.http import _func_

from . import exceptions
from . import downloader

from .autoplaylist import AutoPlaylist
from .config import Config, ConfigDefaults
from .constructs import SkipState, Response, VoiceStateUpdate
from .email import Email
from .entry import StreamPlaylistEntry
from .opus_loader import load_opus_lib
from .permissions import Permissions, PermissionsDefaults
from .player import MusicPlayer
from .playlist import Playlist
from .song import Song
from .sqlfactory import SqlFactory
from .user import User
from .utils import load_file, write_file, sane_round_int, fixg, ftimedelta, get_cur_dt_tm, null_check_string
from .yti import YouTubeIntegration

from .constants import VERSION as BOTVERSION
from .constants import DISCORD_MSG_CHAR_LIMIT, AUDIO_CACHE_PATH, BACKUP_PATH

load_opus_lib()
log = logging.getLogger(__name__)

class MusicBot(discord.Client):

    def __init__(self, config_file=None, perms_file=None):

        if config_file is None:
            config_file = ConfigDefaults.options_file

        if perms_file is None:
            perms_file = PermissionsDefaults.perms_file

        random.seed(datetime.now())

        self.players = {}
        self.exit_signal = None
        self.init_ok = False
        self.cached_app_info = None
        self.last_status = None

        self.config = Config(config_file)
        self.permissions = Permissions(perms_file, grant_all=[self.config.owner_id])

        self.blacklist = set(load_file(self.config.blacklist_file))
        #self.autoplaylist = load_file(self.config.auto_playlist_file)

        self.aiolocks = defaultdict(asyncio.Lock)
        self.downloader = downloader.Downloader(download_folder=AUDIO_CACHE_PATH)

        self._setup_logging()

        self.autoplaylist = AutoPlaylist()

        # Users
        self.ghost_list = {}

        # Metadata
        self.metaData = {}
        self.wholeMetadata = load_file(self.config.metadata_file)

        self.email_util = Email()

        if not self.autoplaylist.songs:
            log.warning("[__INIT__] Autoplaylist is empty, disabling.")
            self.config.auto_playlist = False
        else:
            log.info("[__INIT__] Loaded autoplaylist with {} entries".format(len(self.autoplaylist.songs)))            

        if self.blacklist:
            log.debug("[__INIT__] Loaded blacklist with {} entries".format(len(self.blacklist)))
            
        #Setting up the metaData tags
        if not self.wholeMetadata:
            log.warning("[__INIT__] Metadata tags are empty")
        else:
            temp = True
            for row in self.wholeMetadata:
                if temp == True:
                    self.metaData[row] = []
                    temp = row
                else:
                    urlList = row.split(", ")
                    for addurl in urlList:
                        self.metaData[temp].append(addurl)
                    temp = True

        # TODO: Do these properly
        ssd_defaults = {
            'last_np_msg': None,
            'auto_paused': False,
            'availability_paused': False
        }
        self.server_specific_data = defaultdict(ssd_defaults.copy)

        super().__init__()
        self.aiosession = aiohttp.ClientSession(loop=self.loop)
        self.http.user_agent += ' MusicBot/%s' % BOTVERSION

    def check_url(self, url):
        if url:
            if 'www.' in url and 'https://' not in url:
                url = 'https://' + url
            if '?t=' in url:            
                url = url.split('?t=')[0]
            if '&t' in url or '&index' in url or '&list' in url:
                url = url.split('&')[0]
        return url

    async def dump_metadata_dict(self):
        for each_key in self.metaData.keys():
            for each_value in self.metaData[each_key]:
                if ':' in each_key:
                    each_key = ':' + each_key.split(':')[1] + ':'
                log.info('INSERT INTO MOOD_SONG VALUES (\'' + each_key + '\', \'' + each_value + '\', NOW());')

    async def delete_user(self, user_id):
        return await self.autoplaylist.sqlfactory.user_delete(user_id)

    async def test_db_create(self):
        #status = await self.autoplaylist.sqlfactory.email_create('696969', 'gene-test', 'test-contents', get_cur_dt_tm())
        status = await self.autoplaylist.sqlfactory.user_song_create('181268300301336576', 'test.com', '0', get_cur_dt_tm())
        #await self.autoplaylist.sqlfactory.mood_create('gene-test', get_cur_dt_tm(), get_cur_dt_tm())
        print('Success!' if status else 'Failure :(')

    async def test_db_read(self):
        result = await self.autoplaylist.sqlfactory.user_song_read('181268300301336576', 'test.com')
        print(result)
        #await self.autoplaylist.sqlfactory.mood_create('gene-test', get_cur_dt_tm(), get_cur_dt_tm())
        print('Success!' if result else 'Failure :(')

    async def test_db_update(self):
        status = await self.autoplaylist.sqlfactory.user_song_update('123123123', 'test2.com', '1', get_cur_dt_tm(), '181268300301336576', 'test.com')
        #await self.autoplaylist.sqlfactory.mood_create('gene-test', get_cur_dt_tm(), get_cur_dt_tm())
        print('Success!' if status else 'Failure :(')

    async def test_db_delete(self):
        #status = await self.autoplaylist.sqlfactory.email_delete('696969')
        status = await self.autoplaylist.sqlfactory.user_song_delete('181268300301336576', 'test.com')
        print('Success!' if status else 'Failure :(')

    async def test_db_execute(self):
        url = 'https://www.youtube.com/watch?v=12oatTc6aI'
        success, result_set = await self.autoplaylist.sqlfactory.execute('SELECT COUNT(*) FROM USER_SONG WHERE URL = %s', [url])
        print('Success: {}, RS: {}'.format(str(success), str(result_set)))
        count = result_set[0]
        print(str(count))

    async def dump_bootstrap(self):
        await self.dump_song("Green light")

    async def dump_song(self, kwargs):
        log.debug("#######DEBUG SONG START########")
        my_songs = await self.find_songs_by_title(kwargs)
        for each_song in my_songs:
            log.debug(null_check_string(each_song, 'title'))
            log.debug(null_check_string(each_song, 'url'))
            log.debug(str(await self.autoplaylist.get_likers(each_song.url)))
            log.debug("---")

        log.debug("@@@@@@@@")

        my_song = await self.autoplaylist.find_song_by_url(kwargs)
        if (my_song == None):
            log.debug("MY_SONG NULL")
        else:
            log.debug(null_check_string(my_song, 'title'))
            log.debug(null_check_string(my_song, 'url'))
            log.debug(str(await self.autoplaylist.get_likers(my_song.url)))
            log.debug("---")

        log.debug("########DEBUG SONG END#########")

    ########################
    # updateMetaData
    #
    # Grabs the updated metaData tags
    #
    # Precondition:
    # Postcondition: self.metaData contains newest list
    ########################
    def updateMetaData(self):
        self.wholeMetadata = load_file(self.config.metadata_file)
        if not self.wholeMetadata:
            print("Attention: Metadata tags are empty")
        else:
            temp = True
            for row in self.wholeMetadata:
                if temp == True:
                    self.metaData[row] = []
                    temp = row
                else:
                    urlList = row.split(", ")
                    for addurl in urlList:
                        self.metaData[temp].append(addurl)
                    temp = True

    def is_whitelist_error(self, error_msg):
        whitelist_strings = [ 
            "This video is no longer available because the YouTube account associated with this video has been terminated",
            "This video is unavailable",
            "This video is no longer available due to a copyright claim",
            "The uploader has not made this video available",
            "This video contains content from",
            "The YouTube account associated with this video has been terminated due to multiple third-party notifications of copyright infringement"
        ]

        if type(error_msg) != str:
            error_msg = str(error_msg)

        for each_string in whitelist_strings:
            if each_string in error_msg:
                return True

        return False

    # due to a latency in the YouTube API, this shouldn't be used.
    def test_yti_pl(self):
        yti = YouTubeIntegration() 

        # Creates users' playlists in youtube if they dont have one
        for each_user in self.users_list:
            if each_user:
                if each_user.user_name:
                    name = each_user.user_name.replace(' ', '-')
                    playlist_id = yti.lookup_playlist(each_user.user_id)
                    if playlist_id == None:
                        log.debug("Creating playlist for user: {} {}".format(name, str(each_user)))
                        #yti.create_playlist(name.replace(' ', '-'), each_user.user_id)
                    else:
                        log.warning("Playlist exists for user {} {} ".format(name, str(each_user)))

    async def test_yti_songs(self):
        yti = YouTubeIntegration() 

        # Creates users' playlists in youtube if they dont have one
        for each_user in self.users_list:
            if each_user:
                if each_user.user_name:
                    name = each_user.user_name.replace(' ', '-')
                    playlist_id = yti.lookup_playlist(each_user.user_id)
                    if playlist_id == None:
                        log.debug("Creating playlist for user: {} {}".format(name, str(each_user)))
                        #yti.create_playlist(name.replace(' ', '-'), each_user.user_id)
                    else:
                        log.warning("Playlist exists for user {} {} ".format(name, str(each_user)))

                    song_list = await self.autoplaylist.get_user_songs(each_user.user_id)
                    if song_list:
                        for each_song in song_list:
                            if type(each_song) == Song:
                                each_url = each_song.url
                                log.error("Song{} in user's{} list is a Song obj, extracting URL".format(each_song, name))                        

                            if "youtube" in each_url or "youtu.be" in each_url:
                                video_id = yti.extract_youtube_video_id(each_url)
                                if video_id != None:
                                    video_playlist_id = yti.lookup_video(video_id, playlist_id)
                                    if video_playlist_id == None:
                                        log.debug("yti.add_video({}, {})".format(name, video_id))
                                        #yti.add_video(each_user.user_id, video_id)
                                        time.sleep(.500)
                                else:
                                    log.warning("video_id is None")
                            else:
                                #print("Not a youtube URL: " + each_song)
                                pass
                    else:
                        #log.error(each_user + " has no songs")
                        pass
                else:
                    #log.error(each_user)
                    pass

    # due to a latency in the YouTube API, this shouldn't be used.
    def init_yti_pl(self):
        yti = YouTubeIntegration() 

        # Creates users' playlists in youtube if they dont have one
        for each_user in self.users_list:
            if each_user:
                if each_user.user_name:
                    name = each_user.user_name.replace(' ', '-')
                    playlist_id = yti.lookup_playlist(each_user.user_id)
                    if playlist_id == None:
                        log.debug("Creating playlist for user: " + name)
                        yti.create_playlist(name.replace(' ', '-'), each_user.user_id)
                    else:
                        log.warning("Playlist exists for user: " + name)

    async def init_yti_songs(self):
        yti = YouTubeIntegration() 

        # Creates users' playlists in youtube if they dont have one
        for each_user in self.users_list:
            if each_user:
                if each_user.user_name:
                    name = each_user.user_name.replace(' ', '-')
                    playlist_id = yti.lookup_playlist(each_user.user_id)
                    if playlist_id == None:
                        log.debug("Creating playlist for user: {} {}".format(name, str(each_user)))
                        yti.create_playlist(name.replace(' ', '-'), each_user.user_id)
                    else:
                        log.warning("Playlist exists for user {} {} ".format(name, str(each_user)))

                    song_list = await self.autoplaylist.get_user_songs(each_user.user_id)
                    for each_song in song_list:
                        if type(each_song) == Song:
                            each_url = each_song.url
                            log.error("Song{} in user's{} list is a Song obj, extracting URL".format(each_song, name))                        

                        if "youtube" in each_url or "youtu.be" in each_url:
                            video_id = yti.extract_youtube_video_id(each_url)
                            if video_id != None:
                                video_playlist_id = yti.lookup_video(video_id, playlist_id)
                                if video_playlist_id == None:
                                    #log.debug("yti.add_video({}, {})".format(name, video_id))
                                    yti.add_video(each_user.user_id, video_id)
                                    #time.sleep(.500)
                            else:
                                log.warning("video_id is None")
                        else:
                            #log.error("Not a youtube URL: " + each_song)
                            pass
                    else:
                        #log.error(each_user + " has no songs")
                        pass
                else:
                    #log.error(each_user)
                    pass

    async def notify_likers(self, song, emsg=""):
        if song == None:
            log.debug("Null song, no one to notify")
            return

        channel = self.get_channel(list(self.config.bound_channels)[0])

        likers = await self.autoplaylist.get_likers(song.url)
        likers_str = ""

        if likers:
            #likers = list(filter(lambda liker: self._get_user(liker.user_id) != None, likers))
            likers = list(filter(None, [ self._get_user(liker.user_id) for liker in likers ]))
            log.warning(str(likers))
            for each_liker in likers:
                likers_str += each_liker.mention + " "

            msg = 'Hey! %s. It seems like your video has been made unavailable.\n%s, %s\nReason: %s' % (likers_str, null_check_string(song, 'title'), null_check_string(song, 'url'), emsg)

            await self.safe_send_message(channel, msg)

    def __del__(self):
        # These functions return futures but it doesn't matter
        try:    self.http.session.close()
        except: pass

        try:    self.aiosession.close()
        except: pass

    # TODO: Add some sort of `denied` argument for a message to send when someone else tries to use it
    def owner_only(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Only allow the owner to use these commands
            orig_msg = _get_variable('message')

            if not orig_msg or orig_msg.author.id == self.config.owner_id:
                # noinspection PyCallingNonCallable
                return await func(self, *args, **kwargs)
            else:
                raise exceptions.PermissionsError("only the owner can use this command", expire_in=30)
        return wrapper

    def dev_only(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            orig_msg = _get_variable('message')

            if orig_msg.author.id in self.config.dev_ids:
                # noinspection PyCallingNonCallable
                return await func(self, *args, **kwargs)
            else:
                raise exceptions.PermissionsError("only dev users can use this command", expire_in=30)

        wrapper.dev_cmd = True
        return wrapper

    def ensure_appinfo(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            await self._cache_app_info()
            # noinspection PyCallingNonCallable
            return await func(self, *args, **kwargs)

        return wrapper

    def _get_user(self, user_id, voice=False):

        if voice:
            for server in self.servers:
                for channel in server.channels:
                    for m in channel.voice_members:
                        if m.id == user_id:
                            return m
        else:
            return discord.utils.find(lambda m: m.id == user_id, self.get_all_members())

    def _get_channel(self, user_id, voice=False):
        if voice:
            for server in self.servers:
                for channel in server.channels:
                    for m in channel.voice_members:
                        if m.id == user_id:
                            return channel
        else:
            return discord.utils.find(lambda m: m.id == user_id, self.get_all_members())

    def _get_owner(self, *, server=None, voice=False):
        return discord.utils.find(
            lambda m: m.id == self.config.owner_id and (m.voice_channel if voice else True),
            server.members if server else self.get_all_members()
        )

    async def _get_restarter(self, voice=False):

        for server in self.servers:
            if server:
                tchans = []
                for chan in server.channels:
                    if chan:
                        if chan.type == discord.ChannelType.text:
                            tchans.append(chan)

                for channel in tchans:
                    async for message in self.logs_from(channel, limit=50, before=datetime.utcnow(), reverse=False):
                        if message.content.startswith(self.config.command_prefix +'restart'):
                            return message.author
        return None

    def _delete_old_audiocache(self, path=AUDIO_CACHE_PATH):
        try:
            shutil.rmtree(path)
            return True
        except:
            try:
                os.rename(path, path + '__')
            except:
                return False
            try:
                shutil.rmtree(path)
            except:
                os.rename(path + '__', path)
                return False

        return True

    def _setup_logging(self):
        if len(logging.getLogger(__package__).handlers) > 1:
            log.debug("Skipping logger setup, already set up")
            return

        shandler = logging.StreamHandler(stream=sys.stdout)
        shandler.setFormatter(colorlog.LevelFormatter(
            fmt = {
                'DEBUG': '{log_color}[{levelname}:{module}] {message}',
                'INFO': '{log_color}{message}',
                'WARNING': '{log_color}{levelname}: {message}',
                'ERROR': '{log_color}[{levelname}:{module}] {message}',
                'CRITICAL': '{log_color}[{levelname}:{module}] {message}',

                'EVERYTHING': '{log_color}[{levelname}:{module}] {message}',
                'NOISY': '{log_color}[{levelname}:{module}] {message}',
                'VOICEDEBUG': '{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}',
                'FFMPEG': '{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}'
            },
            log_colors = {
                'DEBUG':    'cyan',
                'INFO':     'white',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'bold_red',

                'EVERYTHING': 'white',
                'NOISY':      'white',
                'FFMPEG':     'bold_purple',
                'VOICEDEBUG': 'purple',
        },
            style = '{',
            datefmt = ''
        ))
        shandler.setLevel(self.config.debug_level)
        logging.getLogger(__package__).addHandler(shandler)

        ehandler = logging.FileHandler('logs/{date}.{package}.err.log'.format(
            date=datetime.today().strftime('%Y-%m-%d'), package=__package__), encoding='utf-8', mode='a')
        ehandler.setFormatter(logging.Formatter('{asctime} [{levelname}:{name}] {message}', style='{'))
        ehandler.setLevel(logging.WARNING)
        logging.getLogger(__package__).addHandler(ehandler)

        fhandler = logging.FileHandler('logs/{date}.{package}.log'.format(
            date=datetime.today().strftime('%Y-%m-%d'), package=__package__), encoding='utf-8', mode='a')
        fhandler.setFormatter(logging.Formatter('{asctime} [{levelname}:{name}] {message}', style='{'))
        fhandler.setLevel(logging.DEBUG)
        logging.getLogger(__package__).addHandler(fhandler)

        log.debug("Set logging level to {}".format(self.config.debug_level_str))

        if self.config.debug_mode:
            dlogger = logging.getLogger('discord')
            dlogger.setLevel(logging.DEBUG)
            dhandler = logging.FileHandler(filename='logs/discord.log', encoding='utf-8', mode='w')
            dhandler.setFormatter(logging.Formatter('{asctime}:{levelname}:{name}: {message}', style='{'))
            dlogger.addHandler(dhandler)

        logging.getLogger(__package__).addHandler(watchtower.CloudWatchLogHandler())

    @staticmethod
    def _check_if_empty(vchannel: discord.Channel, *, excluding_me=True, excluding_deaf=False):
        def check(member):
            if excluding_me and member == vchannel.server.me:
                return False

            if excluding_deaf and any([member.deaf, member.self_deaf]):
                return False

            return True

        return not sum(1 for m in vchannel.voice_members if check(m))

    async def _join_startup_channels(self, channels, *, autosummon=True):
        joined_servers = set()
        channel_map = {c.server: c for c in channels}

        def _autopause(player):
            if self._check_if_empty(player.voice_client.channel):
                log.info("Initial autopause in empty channel")

                player.pause()
                self.server_specific_data[player.voice_client.channel.server]['auto_paused'] = True

        for server in self.servers:
            if server.unavailable or server in channel_map:
                continue

            if server.me.voice_channel:
                log.info("Found resumable voice channel {0.server.name}/{0.name}".format(server.me.voice_channel))
                channel_map[server] = server.me.voice_channel

            if autosummon:
                owner = self._get_owner(server=server, voice=True)
                if owner:
                    log.info("Found owner in \"{}\"".format(owner.voice_channel.name))
                    channel_map[server] = owner.voice_channel

                if not owner:
                    restarter = await self._get_restarter(voice=True) or await self._get_restarter()

                    if restarter:
                        log.info("Found restarter {} in \"{}\"".format(restarter.name, self._get_channel(restarter.id)))
                        channel_map[server] = restarter.voice_channel

        for server, channel in channel_map.items():
            if server in joined_servers:
                log.info("Already joined a channel in \"{}\", skipping".format(server.name))
                continue

            if channel and channel.type == discord.ChannelType.voice:
                log.info("Attempting to join {0.server.name}/{0.name}".format(channel))

                chperms = channel.permissions_for(server.me)

                if not chperms.connect:
                    log.info("Cannot join channel \"{}\", no permission.".format(channel.name))
                    continue

                elif not chperms.speak:
                    log.info("Will not join channel \"{}\", no permission to speak.".format(channel.name))
                    continue

                try:
                    player = await self.get_player(channel, create=True, deserialize=self.config.persistent_queue)
                    joined_servers.add(server)

                    log.info("Joined {0.server.name}/{0.name}".format(channel))

                    if player.is_stopped:
                        player.play()

                    if self.config.auto_playlist and not player.playlist.entries:
                        await self.on_player_finished_playing(player)
                        if self.config.auto_pause:
                            player.once('play', lambda player, **_: _autopause(player))

                except Exception:
                    log.debug("Error joining {0.server.name}/{0.name}".format(channel), exc_info=True)
                    log.error("Failed to join {0.server.name}/{0.name}".format(channel))

            elif channel:
                log.warning("Not joining {0.server.name}/{0.name}, that's a text channel.".format(channel))

            else:
                log.warning("Invalid channel thing: {}".format(channel))

    async def _wait_delete_msg(self, message, after):
        await asyncio.sleep(after)
        await self.safe_delete_message(message, quiet=True)

    async def _wait_delete_msgs(self, messages, after):
        await asyncio.sleep(after)
        try:
            if len(messages) == 1:
                await self.delete_message(messages[0])
            else:
                for msg in messages:
                    await self.delete_message(msg)
                #await self.delete_messages(messages)
        except Exception as e:
            print("Something went wrong: ", e)

    # TODO: Check to see if I can just move this to on_message after the response check
    async def _manual_delete_check(self, message, *, quiet=False):
        if self.config.delete_invoking:
            await self.safe_delete_message(message, quiet=quiet)

    async def _check_ignore_non_voice(self, msg):
        vc = msg.server.me.voice_channel

        # If we've connected to a voice chat and we're in the same voice channel
        if not vc or vc == msg.author.voice_channel:
            return True
        else:
            raise exceptions.PermissionsError(
                "you cannot use this command when not in the voice channel (%s)" % vc.name, expire_in=30)

    async def _cache_app_info(self, *, update=False):
        if not self.cached_app_info and not update and self.user.bot:
            log.debug("Caching app info")
            self.cached_app_info = await self.application_info()

        return self.cached_app_info


    @ensure_appinfo
    async def generate_invite_link(self, *, permissions=discord.Permissions(70380544), server=None):
        return discord.utils.oauth_url(self.cached_app_info.id, permissions=permissions, server=server)

    async def join_voice_channel(self, channel):
        if isinstance(channel, discord.Object):
            channel = self.get_channel(channel.id)

        if getattr(channel, 'type', ChannelType.text) != ChannelType.voice:
            raise discord.InvalidArgument('Channel passed must be a voice channel')

        server = channel.server

        if self.is_voice_connected(server):
            raise discord.ClientException('Already connected to a voice channel in this server')

        def session_id_found(data):
            user_id = data.get('user_id')
            guild_id = data.get('guild_id')
            return user_id == self.user.id and guild_id == server.id

        log.voicedebug("(%s) creating futures", _func_())
        # register the futures for waiting
        session_id_future = self.ws.wait_for('VOICE_STATE_UPDATE', session_id_found)
        voice_data_future = self.ws.wait_for('VOICE_SERVER_UPDATE', lambda d: d.get('guild_id') == server.id)

        # "join" the voice channel
        log.voicedebug("(%s) setting voice state", _func_())
        await self.ws.voice_state(server.id, channel.id)

        log.voicedebug("(%s) waiting for session id", _func_())
        session_id_data = await asyncio.wait_for(session_id_future, timeout=30, loop=self.loop)

        # sometimes it gets stuck on this step.  Jake said to wait indefinitely.  To hell with that.
        log.voicedebug("(%s) waiting for voice data", _func_())
        data = await asyncio.wait_for(voice_data_future, timeout=30, loop=self.loop)

        kwargs = {
            'user': self.user,
            'channel': channel,
            'data': data,
            'loop': self.loop,
            'session_id': session_id_data.get('session_id'),
            'main_ws': self.ws
        }

        voice = discord.VoiceClient(**kwargs)
        try:
            log.voicedebug("(%s) connecting...", _func_())
            with aiohttp.Timeout(30):
                await voice.connect()

        except asyncio.TimeoutError as e:
            log.voicedebug("(%s) connection failed, disconnecting", _func_())
            try:
                await voice.disconnect()
            except:
                pass
            raise e

        log.voicedebug("(%s) connection successful", _func_())

        self.connection._add_voice_client(server.id, voice)
        return voice

    async def get_voice_client(self, channel: discord.Channel):
        if isinstance(channel, discord.Object):
            channel = self.get_channel(channel.id)

        if getattr(channel, 'type', ChannelType.text) != ChannelType.voice:
            raise AttributeError('Channel passed must be a voice channel')

        async with self.aiolocks[_func_() + ':' + channel.server.id]:
            if self.is_voice_connected(channel.server):
                return self.voice_client_in(channel.server)

            vc = None
            t0 = t1 = 0
            tries = 5

            for attempt in range(1, tries+1):
                log.debug("Connection attempt {} to {}".format(attempt, channel.name))
                t0 = time.time()

                try:
                    vc = await self.join_voice_channel(channel)
                    t1 = time.time()
                    break

                except asyncio.TimeoutError:
                    log.warning("Failed to connect, retrying ({}/{})".format(attempt, tries))

                    # TODO: figure out if I need this or not
                    # try:
                    #     await self.ws.voice_state(channel.server.id, None)
                    # except:
                    #     pass

                except:
                    log.exception("Unknown error attempting to connect to voice")

                await asyncio.sleep(0.5)

            if not vc:
                log.critical("Voice client is unable to connect, restarting...")
                await self.restart()

            log.debug("Connected in {:0.1f}s".format(t1-t0))
            log.info("Connected to {}/{}".format(channel.server, channel))

            vc.ws._keep_alive.name = 'VoiceClient Keepalive'

            return vc

    async def reconnect_voice_client(self, server, *, sleep=0.1, channel=None):
        log.debug("Reconnecting voice client on \"{}\"{}".format(
            server, ' to "{}"'.format(channel.name) if channel else ''))

        async with self.aiolocks[_func_() + ':' + server.id]:
            vc = self.voice_client_in(server)

            if not (vc or channel):
                return

            _paused = False
            player = self.get_player_in(server)

            if player and player.is_playing:
                log.voicedebug("(%s) Pausing", _func_())

                player.pause()
                _paused = True

            log.voicedebug("(%s) Disconnecting", _func_())

            try:
                await vc.disconnect()
            except:
                pass

            if sleep:
                log.voicedebug("(%s) Sleeping for %s", _func_(), sleep)
                await asyncio.sleep(sleep)

            if player:
                log.voicedebug("(%s) Getting voice client", _func_())

                if not channel:
                    new_vc = await self.get_voice_client(vc.channel)
                else:
                    new_vc = await self.get_voice_client(channel)

                log.voicedebug("(%s) Swapping voice client", _func_())
                await player.reload_voice(new_vc)

                if player.is_paused and _paused:
                    log.voicedebug("Resuming")
                    player.resume()

        log.debug("Reconnected voice client on \"{}\"{}".format(
            server, ' to "{}"'.format(channel.name) if channel else ''))

    async def disconnect_voice_client(self, server):
        vc = self.voice_client_in(server)
        if not vc:
            return

        if server.id in self.players:
            self.players.pop(server.id).kill()

        await vc.disconnect()

    async def disconnect_all_voice_clients(self):
        for vc in list(self.voice_clients).copy():
            await self.disconnect_voice_client(vc.channel.server)

    async def set_voice_state(self, vchannel, *, mute=False, deaf=False):
        if isinstance(vchannel, discord.Object):
            vchannel = self.get_channel(vchannel.id)

        if getattr(vchannel, 'type', ChannelType.text) != ChannelType.voice:
            raise AttributeError('Channel passed must be a voice channel')

        await self.ws.voice_state(vchannel.server.id, vchannel.id, mute, deaf)
        # I hope I don't have to set the channel here
        # instead of waiting for the event to update it

    def get_player_in(self, server: discord.Server) -> MusicPlayer:
        return self.players.get(server.id)

    async def get_player(self, channel, create=False, *, deserialize=False) -> MusicPlayer:
        server = channel.server

        async with self.aiolocks[_func_() + ':' + server.id]:
            if deserialize:
                voice_client = await self.get_voice_client(channel)
                player = await self.deserialize_queue(server, voice_client)

                if player:
                    log.debug("Created player via deserialization for server %s with %s entries", server.id, len(player.playlist))
                    # Since deserializing only happens when the bot starts, I should never need to reconnect
                    return self._init_player(player, server=server)

            if server.id not in self.players:
                if not create:
                    raise exceptions.CommandError(
                        'The bot is not in a voice channel.  '
                        'Use %ssummon to summon it to your voice channel.' % self.config.command_prefix)

                voice_client = await self.get_voice_client(channel)

                playlist = Playlist(self)
                player = MusicPlayer(self, voice_client, playlist)
                self._init_player(player, server=server)

            async with self.aiolocks[self.reconnect_voice_client.__name__ + ':' + server.id]:
                if self.players[server.id].voice_client not in self.voice_clients:
                    log.debug("Reconnect required for voice client in {}".format(server.name))
                    await self.reconnect_voice_client(server, channel=channel)

        return self.players[server.id]

    def _init_player(self, player, *, server=None):
        player = player.on('play', self.on_player_play) \
                       .on('resume', self.on_player_resume) \
                       .on('pause', self.on_player_pause) \
                       .on('stop', self.on_player_stop) \
                       .on('finished-playing', self.on_player_finished_playing) \
                       .on('entry-added', self.on_player_entry_added) \
                       .on('error', self.on_player_error)

        player.skip_state = SkipState()

        if server:
            self.players[server.id] = player

        return player

    async def on_player_play(self, player, entry):
        await self.update_now_playing_status(entry)
        player.skip_state.reset()

        # This is the one event where its ok to serialize autoplaylist entries
        await self.serialize_queue(player.voice_client.channel.server)

        channel = entry.meta.get('channel', None)
        author = entry.meta.get('author', None)

        # updates title if it's not there
        song = await self.autoplaylist.find_song_by_url(entry.url)
        if song:
            if not song.title or song.title == "" or entry.title != song.title:
                log.info("[ON_PLAYER_PLAY] Updating title from {old_title} to {new_title} for {url}".format(old_title=song.title, new_title=entry.title, url=entry.url))
                song.title = entry.title
                if not await self.autoplaylist.sqlfactory.song_update(song.url, song.title, song.play_count, song.volume, get_cur_dt_tm(), song.cret_dt_tm, song.url):
                    log.error('Failed to update song {} with new title {}'.format(entry.url, entry.title))
            player.volume = song.volume

        if channel and author:
            last_np_msg = self.server_specific_data[channel.server]['last_np_msg']
            if last_np_msg and last_np_msg.channel == channel:

                async for lmsg in self.logs_from(channel, limit=1):
                    if lmsg != last_np_msg and last_np_msg:
                        await self.safe_delete_message(last_np_msg)
                        self.server_specific_data[channel.server]['last_np_msg'] = None
                    break  # This is probably redundant

            if self.config.now_playing_mentions:
                newmsg = '%s - your song **%s** is now playing in %s!' % (
                    entry.meta['author'].mention, entry.title, player.voice_client.channel.name)
            else:
                newmsg = 'Now playing in %s: **%s**' % (
                    player.voice_client.channel.name, entry.title)

            if self.server_specific_data[channel.server]['last_np_msg']:
                self.server_specific_data[channel.server]['last_np_msg'] = await self.safe_edit_message(last_np_msg, newmsg, send_if_fail=True)
            else:
                self.server_specific_data[channel.server]['last_np_msg'] = await self.safe_send_message(channel, newmsg)

        # TODO: Check channel voice state?

    async def on_player_resume(self, player, entry, **_):
        await self.update_now_playing_status(entry)

    async def on_player_pause(self, player, entry, **_):
        await self.update_now_playing_status(entry, True)
        await self.serialize_queue(player.voice_client.channel.server)

    async def on_player_stop(self, player, **_):
        await self.update_now_playing_status()

    async def on_player_finished_playing(self, player, **_):

        # reset volume
        player.volume = self.config.default_volume

        if len(player.playlist.entries) == 0 and not player.current_entry and self.config.auto_playlist:

            timeout = 0
            while self.autoplaylist.songs and timeout < 100 and not player.is_paused:

                # looking for people in the channel to choose who song gets played
                people = [m for m in player.voice_client.channel.voice_members if not (m.deaf or m.self_deaf or m.id == self.user.id)]
                log.debug('People: ' + str(people))

                ####################
                # Ghost begin
                ####################
                copy_ghost_list = self.ghost_list.copy()
                for author_fakePPL in copy_ghost_list.keys():
                    #Check if the author of the list is still in the channel
                    if not list(filter(lambda objId: author_fakePPL == objId.id, player.voice_client.channel.voice_members)):
                        del self.ghost_list[author_fakePPL]
                        continue
                    for fakePPL in copy_ghost_list[author_fakePPL]:
                        #Checks if the ghost is in the channel (remove them from the list if they are)
                        if list(filter(lambda objId: fakePPL == objId.id, player.voice_client.channel.voice_members)):
                            self.ghost_list[author_fakePPL].remove(fakePPL)
                            continue
                        else:
                            people.append(fakePPL)
                del copy_ghost_list
                ####################
                # Ghost end
                ####################

                # no people in room? try again
                if (len(people) == 0):
                    timeout = timeout + 1
                    continue

                author = random.choice(people)
                log.debug(author)

                # takes discord obj and returns User object
                if author:
                    user = await self.autoplaylist.get_user(author.id)
                if user == None:
                    timeout = timeout + 1
                    continue

                song_list = await self.autoplaylist.get_user_songs(user.user_id)

                if len(song_list) == 0:
                    log.warning("USER HAS NO SONGS IN APL")
                    timeout = timeout + 1
                    continue
                else:
                    # make sure they're in the channel with the bot
                    if self._get_user(author.id, voice=True) and (self._get_channel(author.id, voice=True) == self._get_channel(self.user.id, voice=True)):
                        log.debug(self._get_user(author.id, voice=True))

                        # apparently i dont have the links set up correctly
                        #song = random.choice(song_list)

                        ####################
                        # Mood begin
                        ####################
                        # if user's mood isn't the default setting (None)
                        if user.mood != None:
                            log.debug("MOOD: " + null_check_string(user, 'mood'))

                            if user.mood.lower() in self.metaData.keys():
                                song = random.choice(self.metaData[user.mood.lower()])
                            else:
                                prntStr = "The tag **[" + user.mood + "]** does not exist."
                                return Response(prntStr, delete_after=35)
                        ####################
                        # Mood end
                        ####################
                        else:
                            song = random.choice(song_list)
                            if song == None:
                                timeout = timeout + 1
                                continue
                            #song = await self.autoplaylist.find_song_by_url(song.url)

                        ####################
                        # Repeat begin
                        ####################
                        if song:
                            log.debug(null_check_string(song, 'title'))
                            #log.debug(str(song.__dict__))
                            
                            if str(song.updt_dt_tm) > (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S'):
                                log.debug("Song played too recently")
                                log.debug('Last Played: {}'.format(song.updt_dt_tm))
                                log.debug('10 days ago: {}'.format((datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')))
                                timeout = timeout + 1
                                continue
                            timeout = 0
                        ####################
                        # Repeat end
                        ####################
                    else:
                        if list(filter(lambda personID: user.user_id in self.ghost_list[personID], self.ghost_list.keys())):
                            log.debug("GHOST IN CHANNEL!")
                            song = random.choice(song_list)
                            #check if repeat song
                            #if any(filter(lambda song_obj : song_obj.url == song.url, self.heard_list)):
                            #    log.debug("Song played too recently")
                            #    timeout = timeout + 1
                            #    continue
                            timeout = 0
                        else:
                            log.warning("USER NOT IN CHANNEL!")
                            log.warning(str(user))
                            log.warning("---")
                            log.debug(self._get_user(author.id, voice=True))
                            log.debug(self._get_channel(author.id, voice=True) == self._get_channel(self.user.id, voice=True))
                            timeout = timeout + 1
                            continue

                info = {}

                ####################
                # Download song begin
                ####################
                try:
                    if song and not song.url:
                        #song.updt_dt_tm = get_cur_dt_tm()
                        pass
                    info = await self.downloader.extract_info(player.playlist.loop, song.url, download=False, process=False)
                    
                except downloader.youtube_dl.utils.DownloadError as e:
                    for each_ele in e.args:
                        log.debug("Error Element: " + each_ele)

                    if 'YouTube said:' in e.args[0]:
                        # url is bork, remove from list and put in removed list
                        log.error("Error processing youtube url:\n{}".format(e.args[0]))

                    else:
                        # Probably an error from a different extractor, but I've only seen youtube's
                        log.error("Error processing \"{url}\": {ex}".format(url=song.url, ex=e.args[0]))

                    if song and self.is_whitelist_error(e):
                        await self.notify_likers(song, str(e))
                        for liker in await self.autoplaylist.get_likers(song.url):
                            log.error("YT DL ERROR - REMOVING SONG {} FROM USER'S {} APL".format(str(song), str(liker)))
                            user = self.autoplaylist.get_user(liker)                            
                            success = await self.autoplaylist.sqlfactory.song_delete(song.url)
                            if not success:
                                log.error("YT DL ERROR [DEBUG] - song[{}], user[{}], liker[{}], song.url[{}]".format(str(song), str(user), str(liker), str(song.url)))
                                log.error("YT DL ERROR - FAILURE to remove song {} from user's {} list".format(str(song), str(user)))
                                self.email_util.send_exception(str(user), str(song), "GENERIC ERROR - Failed to remove song {} from user's {} list".format(str(song), str(user)))
                            else:
                                log.warn("YT DL ERROR - SUCCESS to remove song {} from user's {} list".format(str(song), str(user)))
                        continue
                    else:
                        log.error("YT DL ERROR - Downloading song {} resulted in unknown exception {}".format(str(song), str(e)))
                        self.email_util.send_exception(str(user), str(song), "YT DL ERROR - Downloading song {} resulted in unknown exception {}".format(str(song), str(e)))

                except Exception as e:

                    log.error("Error processing \"{url}\": {ex}".format(url=song.url, ex=e))
                    log.exception(e)

                    if song and self.is_whitelist_error(e):
                        await self.notify_likers(song, str(e))
                        for liker in await self.autoplaylist.get_likers(song.url):
                            user = self.autoplaylist.get_user(liker)
                            success = await self.autoplaylist.sqlfactory.song_delete(song.url)
                            if not success:
                                log.error("GENERIC ERROR [DEBUG] - song[{}], user[{}], liker[{}], song.url[{}]".format(str(song), str(user), str(liker), str(song.url)))
                                log.error("GENERIC ERROR - FAILURE to remove song {} from user's {} list".format(str(song), str(user)))
                                self.email_util.send_exception(str(user), str(song), "GENERIC ERROR - Failed to remove song {} from user's {} list".format(str(song), str(user)))
                            else:
                                log.warn("GENERIC ERROR - SUCCESS to remove song {} from user's {} list".format(str(song), str(user)))
                        continue

                    else:
                        log.error(e)
                        self.email_util.send_exception(str(user), str(song), "UNKNOWN ERROR - Exception: {}".format(str(e)))
                            

                if info.get('entries', None):  # or .get('_type', '') == 'playlist'
                    log.debug("Playlist found but is unsupported at this time, skipping.")
                    # TODO: Playlist expansion

                log.debug('Currently playing: ' + str(song) if player.currently_playing else 'Nothing playing')
                #player.currently_playing = song

                if song:
                    player.volume = song.volume
                    log.info("Stored song volume: %s" % player.volume)

                try:
                    await self._add_entry(player=player, song_url=song.url, channel=None, author=author)
                    break # found our song, we don't need to keep looping
                except exceptions.ExtractionError as e:
                    log.error("Error adding song from autoplaylist: {}".format(e))
                    log.debug('', exc_info=True)

                    if song and self.is_whitelist_error(e):
                        await self.notify_likers(song, str(e))
                        for liker in await self.autoplaylist.get_likers(song.url):
                            user = self.autoplaylist.get_user(liker)
                            success = await self.autoplaylist.sqlfactory.song_delete(song.url)
                            if not success:
                                log.error("GENERIC ERROR - FAILURE to remove song {} from user's {} list".format(str(song), str(user)))
                                self.email_util.send_exception(str(user), str(song), "GENERIC ERROR - Failed to remove song {} from user's {} list".format(str(song), str(user)))
                            else:
                                log.warn("GENERIC ERROR - SUCCESS to remove song {} from user's {} list".format(str(song), str(user)))
                        continue
                    else:
                        log.error(e)
                        self.email_util.send_exception(str(user), str(song), "UNKNOWN EXTRACTION ERROR - Exception: {}".format(str(e)))

                    continue
                except Exception as e:
                    log.error(str(e))              
            
            if not self.autoplaylist.songs:
                # TODO: When I add playlist expansion, make sure that's not happening during this check
                log.warning("No playable songs in the autoplaylist, disabling.")
                self.config.auto_playlist = False

        else: # Don't serialize for autoplaylist events
            log.debug("serializing queue")
            await self.serialize_queue(player.voice_client.channel.server)

    async def on_player_entry_added(self, player, playlist, entry, **_):
        if entry.meta.get('author') and entry.meta.get('channel'):
            await self.serialize_queue(player.voice_client.channel.server)

    async def on_player_error(self, player, entry, ex, **_):
        if 'channel' in entry.meta:
            await self.safe_send_message(
                entry.meta['channel'],
                "```\nError from FFmpeg:\n{}\n```".format(ex)
            )
        else:
            log.exception("Player error", exc_info=ex)

    async def update_now_playing_status(self, entry=None, is_paused=False):
        game = None

        if self.user.bot:
            activeplayers = sum(1 for p in self.players.values() if p.is_playing)
            if activeplayers > 1:
                game = discord.Game(name="music on %s servers" % activeplayers)
                entry = None

            elif activeplayers == 1:
                player = discord.utils.get(self.players.values(), is_playing=True)
                entry = player.current_entry

        if entry:
            prefix = u'\u275A\u275A ' if is_paused else ''

            name = u'{}{}'.format(prefix, entry.title)[:128]
            game = discord.Game(name=name, type=0)

        async with self.aiolocks[_func_()]:
            if game != self.last_status:
                await self.change_presence(game=game)
                self.last_status = game

    async def update_now_playing_message(self, server, message, *, channel=None):
        lnp = self.server_specific_data[server]['last_np_msg']
        m = None

        if message is None and lnp:
            await self.safe_delete_message(lnp, quiet=True)

        elif lnp: # If there was a previous lp message
            oldchannel = lnp.channel

            if lnp.channel == oldchannel: # If we have a channel to update it in
                async for lmsg in self.logs_from(channel, limit=1):
                    if lmsg != lnp and lnp: # If we need to resend it
                        await self.safe_delete_message(lnp, quiet=True)
                        m = await self.safe_send_message(channel, message, quiet=True)
                    else:
                        m = await self.safe_edit_message(lnp, message, send_if_fail=True, quiet=False)

            elif channel: # If we have a new channel to send it to
                await self.safe_delete_message(lnp, quiet=True)
                m = await self.safe_send_message(channel, message, quiet=True)

            else: # we just resend it in the old channel
                await self.safe_delete_message(lnp, quiet=True)
                m = await self.safe_send_message(oldchannel, message, quiet=True)

        elif channel: # No previous message
            m = await self.safe_send_message(channel, message, quiet=True)

        self.server_specific_data[server]['last_np_msg'] = m

    async def serialize_queue(self, server, *, dir=None):
        """
        Serialize the current queue for a server's player to json.
        """

        player = self.get_player_in(server)
        if not player:
            return

        if dir is None:
            dir = 'data/%s/queue.json' % server.id

        async with self.aiolocks['queue_serialization'+':'+server.id]:
            log.debug("Serializing queue for %s", server.id)

            with open(dir, 'w', encoding='utf8') as f:
                f.write(player.serialize(sort_keys=True))

    async def serialize_all_queues(self, *, dir=None):
        coros = [self.serialize_queue(s, dir=dir) for s in self.servers]
        await asyncio.gather(*coros, return_exceptions=True)

    async def deserialize_queue(self, server, voice_client, playlist=None, *, dir=None) -> MusicPlayer:
        """
        Deserialize a saved queue for a server into a MusicPlayer.  If no queue is saved, returns None.
        """

        if playlist is None:
            playlist = Playlist(self)

        if dir is None:
            dir = 'data/%s/queue.json' % server.id

        async with self.aiolocks['queue_serialization' + ':' + server.id]:
            if not os.path.isfile(dir):
                return None

            log.debug("Deserializing queue for %s", server.id)

            with open(dir, 'r', encoding='utf8') as f:
                data = f.read()

        return MusicPlayer.from_json(data, self, voice_client, playlist)

    @ensure_appinfo
    async def _on_ready_sanity_checks(self):
        # Ensure folders exist
        await self._scheck_ensure_env()

        # Server permissions check
        await self._scheck_server_permissions()

        # playlists in autoplaylist
        await self._scheck_autoplaylist()

        # config/permissions async validate?
        await self._scheck_configs()


    async def _scheck_ensure_env(self):
        log.debug("Ensuring data folders exist")
        for server in self.servers:
            pathlib.Path('data/%s/' % server.id).mkdir(exist_ok=True)

        with open('data/server_names.txt', 'w', encoding='utf8') as f:
            for server in sorted(self.servers, key=lambda s:int(s.id)):
                f.write('{:<22} {}\n'.format(server.id, server.name))

        if not self.config.save_videos and os.path.isdir(AUDIO_CACHE_PATH):
            if self._delete_old_audiocache():
                log.debug("Deleted old audio cache")
            else:
                log.debug("Could not delete old audio cache, moving on.")


    async def _scheck_server_permissions(self):
        log.debug("Checking server permissions")
        pass # TODO

    async def _scheck_autoplaylist(self):
        log.debug("Auditing autoplaylist")
        pass # TODO

    async def _scheck_configs(self):
        log.debug("Validating config")
        await self.config.async_validate(self)

        log.debug("Validating permissions config")
        await self.permissions.async_validate(self)

    async def safe_send_message(self, dest, content, **kwargs):
        tts = kwargs.pop('tts', False)
        quiet = kwargs.pop('quiet', False)
        expire_in = kwargs.pop('expire_in', 0)
        allow_none = kwargs.pop('allow_none', True)
        also_delete = kwargs.pop('also_delete', None)

        msg = None
        lfunc = log.debug if quiet else log.warning

        try:
            if content is not None or allow_none:
                msg = await self.send_message(dest, content, tts=tts)

        except discord.Forbidden:
            lfunc("Cannot send message to \"%s\", no permission", dest.name)

        except discord.NotFound:
            lfunc("Cannot send message to \"%s\", invalid channel?", dest.name)

        except discord.HTTPException:
            if len(content) > DISCORD_MSG_CHAR_LIMIT:
                lfunc("Message is over the message size limit (%s)", DISCORD_MSG_CHAR_LIMIT)
            else:
                lfunc("Failed to send message")
                log.noise("Got HTTPException trying to send message to %s: %s", dest, content)

        finally:
            if msg and expire_in:
                asyncio.ensure_future(self._wait_delete_msg(msg, expire_in))

            if also_delete and isinstance(also_delete, discord.Message):
                asyncio.ensure_future(self._wait_delete_msg(also_delete, expire_in))

        return msg

    async def safe_delete_message(self, message, *, quiet=False):
        lfunc = log.debug if quiet else log.warning

        try:
            return await self.delete_message(message)

        except discord.Forbidden:
            lfunc("Cannot delete message \"{}\", no permission".format(message.clean_content))

        except discord.NotFound:
            lfunc("Cannot delete message \"{}\", message not found".format(message.clean_content))

    async def safe_edit_message(self, message, new, *, send_if_fail=False, quiet=False):
        lfunc = log.debug if quiet else log.warning

        try:
            return await self.edit_message(message, new)

        except discord.NotFound:
            lfunc("Cannot edit message \"{}\", message not found".format(message.clean_content))
            if send_if_fail:
                lfunc("Sending message instead")
                return await self.safe_send_message(message.channel, new)

    async def send_typing(self, destination):
        try:
            return await super().send_typing(destination)
        except discord.Forbidden:
            log.warning("Could not send typing to {}, no permission".format(destination))

    async def edit_profile(self, **fields):
        if self.user.bot:
            return await super().edit_profile(**fields)
        else:
            return await super().edit_profile(self.config._password,**fields)

    async def restart(self):
        self.exit_signal = exceptions.RestartSignal()
        await self.logout()

    def restart_threadsafe(self):
        asyncio.run_coroutine_threadsafe(self.restart(), self.loop)

    def _cleanup(self):
        try:
            self.loop.run_until_complete(self.logout())
        except: pass

        pending = asyncio.Task.all_tasks()
        gathered = asyncio.gather(*pending)

        try:
            gathered.cancel()
            self.loop.run_until_complete(gathered)
            gathered.exception()
        except: pass

    # noinspection PyMethodOverriding
    def run(self):
        try:
            self.loop.run_until_complete(self.start(*self.config.auth))

        except discord.errors.LoginFailure:
            # Add if token, else
            raise exceptions.HelpfulError(
                "Bot cannot login, bad credentials.",
                "Fix your %s in the options file.  "
                "Remember that each field should be on their own line."
                % ['shit', 'Token', 'Email/Password', 'Credentials'][len(self.config.auth)]
            ) #     ^^^^ In theory self.config.auth should never have no items

        finally:
            try:
                self._cleanup()
            except Exception:
                log.error("Error in cleanup", exc_info=True)

            self.loop.close()
            if self.exit_signal:
                raise self.exit_signal

    async def logout(self):
        await self.disconnect_all_voice_clients()
        return await super().logout()

    async def on_error(self, event, *args, **kwargs):
        ex_type, ex, stack = sys.exc_info()

        if ex_type == exceptions.HelpfulError:
            log.error("Exception in {}:\n{}".format(event, ex.message))

            await asyncio.sleep(2)  # don't ask
            await self.logout()

        elif issubclass(ex_type, exceptions.Signal):
            self.exit_signal = ex_type
            await self.logout()

        else:
            log.error("Exception in {}".format(event), exc_info=True)

    async def on_resumed(self):
        log.info("\nReconnected to discord.\n")

    async def on_ready(self):
        dlogger = logging.getLogger('discord')
        for h in dlogger.handlers:
            if getattr(h, 'terminator', None) == '':
                dlogger.removeHandler(h)
                print()

        log.debug("Connection established, ready to go.")

        self.ws._keep_alive.name = 'Gateway Keepalive'

        if self.init_ok:
            log.debug("Received additional READY event, may have failed to resume")
            #return

        await self._on_ready_sanity_checks()
        print()

        log.info('Connected! Musicbot v{}\n'.format(BOTVERSION))

        self.init_ok = True

        ################################

        log.info("Bot:   {0}/{1}#{2}{3}".format(
            self.user.id,
            self.user.name,
            self.user.discriminator,
            ' [BOT]' if self.user.bot else ' [Userbot]'
        ))

        owner = self._get_owner(voice=True) or self._get_owner()
        if owner and self.servers:
            log.info("Owner: {0}/{1}#{2}\n".format(
                owner.id,
                owner.name,
                owner.discriminator
            ))

        elif self.servers:
            log.warning("Owner could not be found on any server (id: %s)\n" % self.config.owner_id)

            log.info('Server List:')
            [log.info(' - ' + s.name) for s in self.servers]

        else:
            log.warning("Owner unknown, bot is not on any servers.")
            if self.user.bot:
                log.warning(
                    "To make the bot join a server, paste this link in your browser. \n"
                    "Note: You should be logged into your main account and have \n"
                    "manage server permissions on the server you want the bot to join.\n"
                    "  " + await self.generate_invite_link()
                )

        print(flush=True)

        if self.config.bound_channels:
            chlist = set(self.get_channel(i) for i in self.config.bound_channels if i)
            chlist.discard(None)

            invalids = set()
            invalids.update(c for c in chlist if c.type == discord.ChannelType.voice)

            chlist.difference_update(invalids)
            self.config.bound_channels.difference_update(invalids)

            if chlist:
                log.info("Bound to text channels:")
                [log.info(' - {}/{}'.format(ch.server.name.strip(), ch.name.strip())) for ch in chlist if ch]
            else:
                print("Not bound to any text channels")

            if invalids and self.config.debug_mode:
                print(flush=True)
                log.info("Not binding to voice channels:")
                [log.info(' - {}/{}'.format(ch.server.name.strip(), ch.name.strip())) for ch in invalids if ch]

            print(flush=True)

        else:
            log.info("Not bound to any text channels")

        if self.config.autojoin_channels:
            chlist = set(self.get_channel(i) for i in self.config.autojoin_channels if i)
            chlist.discard(None)

            invalids = set()
            invalids.update(c for c in chlist if c.type == discord.ChannelType.text)

            chlist.difference_update(invalids)
            self.config.autojoin_channels.difference_update(invalids)

            if chlist:
                log.info("Autojoining voice channels:")
                [log.info(' - {}/{}'.format(ch.server.name.strip(), ch.name.strip())) for ch in chlist if ch]
            else:
                log.info("Not autojoining any voice channels")

            if invalids and self.config.debug_mode:
                print(flush=True)
                log.info("Cannot autojoin text channels:")
                [log.info(' - {}/{}'.format(ch.server.name.strip(), ch.name.strip())) for ch in invalids if ch]

            autojoin_channels = chlist

        else:
            log.info("Not autojoining any voice channels")
            autojoin_channels = set()

        print(flush=True)
        log.info("Options:")

        log.info("  Command prefix: " + self.config.command_prefix)
        log.info("  Default volume: {}%".format(int(self.config.default_volume * 100)))
        log.info("  Skip threshold: {} votes or {}%".format(
            self.config.skips_required, fixg(self.config.skip_ratio_required * 100)))
        log.info("  Now Playing @mentions: " + ['Disabled', 'Enabled'][self.config.now_playing_mentions])
        log.info("  Auto-Summon: " + ['Disabled', 'Enabled'][self.config.auto_summon])
        log.info("  Auto-Playlist: " + ['Disabled', 'Enabled'][self.config.auto_playlist])
        log.info("  Auto-Pause: " + ['Disabled', 'Enabled'][self.config.auto_pause])
        log.info("  Delete Messages: " + ['Disabled', 'Enabled'][self.config.delete_messages])
        if self.config.delete_messages:
            log.info("  Delete Invoking: " + ['Disabled', 'Enabled'][self.config.delete_invoking])
        log.info("  Debug Mode: " + ['Disabled', 'Enabled'][self.config.debug_mode])
        log.info("  Downloaded songs will be " + ['deleted', 'saved'][self.config.save_videos])
        print(flush=True)

        # maybe option to leave the ownerid blank and generate a random command for the owner to use
        # wait_for_message is pretty neato

        await self._join_startup_channels(autojoin_channels, autosummon=self.config.auto_summon)

        # t-t-th-th-that's all folks!

    async def cmd_help(self, command=None):
        """
        Usage:
            {command_prefix}help [command]

        Prints a help message.
        If a command is specified, it prints a help message for that command.
        Otherwise, it lists the available commands.
        """

        if command:
            cmd = getattr(self, 'cmd_' + command, None)
            if cmd and not hasattr(cmd, 'dev_cmd'):
                return Response(
                    "```\n{}```".format(
                        dedent(cmd.__doc__)
                    ).format(command_prefix=self.config.command_prefix),
                    delete_after=60
                )
            else:
                return Response("No such command", delete_after=10)

        else:
            helpmsg = "**Available commands**\n```"
            commands = []

            for att in dir(self):
                if att.startswith('cmd_') and att != 'cmd_help' and not hasattr(getattr(self, att), 'dev_cmd'):
                    command_name = att.replace('cmd_', '').lower()
                    commands.append("{}{}".format(self.config.command_prefix, command_name))

            helpmsg += ", ".join(commands)
            helpmsg += "```\n<https://github.com/SexualRhinoceros/MusicBot/wiki/Commands-list>"
            helpmsg += "You can also use `{}help x` for more info about each command.".format(self.config.command_prefix)

            return Response(helpmsg, reply=True, delete_after=60)

    async def cmd_blacklist(self, message, user_mentions, option, something):
        """
        Usage:
            {command_prefix}blacklist [ + | - | add | remove ] @UserName [@UserName2 ...]

        Add or remove users to the blacklist.
        Blacklisted users are forbidden from using bot commands.
        """

        if not user_mentions:
            raise exceptions.CommandError("No users listed.", expire_in=20)

        if option not in ['+', '-', 'add', 'remove']:
            raise exceptions.CommandError(
                'Invalid option "%s" specified, use +, -, add, or remove' % option, expire_in=20
            )

        for user in user_mentions.copy():
            if user.id == self.config.owner_id:
                print("[Commands:Blacklist] The owner cannot be blacklisted.")
                user_mentions.remove(user)

        old_len = len(self.blacklist)

        if option in ['+', 'add']:
            self.blacklist.update(user.id for user in user_mentions)

            write_file(self.config.blacklist_file, self.blacklist)

            return Response(
                '%s users have been added to the blacklist' % (len(self.blacklist) - old_len),
                reply=True, delete_after=10
            )

        else:
            if self.blacklist.isdisjoint(user.id for user in user_mentions):
                return Response('none of those users are in the blacklist.', reply=True, delete_after=10)

            else:
                self.blacklist.difference_update(user.id for user in user_mentions)
                write_file(self.config.blacklist_file, self.blacklist)

                return Response(
                    '%s users have been removed from the blacklist' % (old_len - len(self.blacklist)),
                    reply=True, delete_after=10
                )

    async def cmd_id(self, author, user_mentions):
        """
        Usage:
            {command_prefix}id [@user]

        Tells the user their id or the id of another user.
        """
        if not user_mentions:
            return Response('your id is `%s`' % author.id, reply=True, delete_after=35)
        else:
            usr = user_mentions[0]
            return Response("%s's id is `%s`" % (usr.name, usr.id), reply=True, delete_after=35)

    @owner_only
    async def cmd_joinserver(self, message, server_link=None):
        """
        Usage:
            {command_prefix}joinserver invite_link

        Asks the bot to join a server.  Note: Bot accounts cannot use invite links.
        """

        if self.user.bot:
            url = await self.generate_invite_link()
            return Response(
                "Bot accounts can't use invite links!  Click here to add me to a server: \n{}".format(url),
                reply=True, delete_after=30
            )

        try:
            if server_link:
                await self.accept_invite(server_link)
                return Response("\N{THUMBS UP SIGN}")

        except:
            raise exceptions.CommandError('Invalid URL provided:\n{}\n'.format(server_link), expire_in=30)

    async def cmd_mood(self, author, leftover_args=None):
        """
        Usage:
        {command_prefix}mood
        {command_prefix}mood TAG
        {command_prefix}mood reset

        mood
        displays your current mood if you have one

        mood happy
        will replace the author's autoplaylist with songs listed in the [happy] tag

        mood reset
        will revert back to the author's autoplaylist

        """
        longStr = ""
        args = str(leftover_args)[2:-2]

        # gets user from self.users_list
        user = self.autoplaylist.get_user(author.id)

        if args is "":
            longStr = "**" + author.display_name + "**, your current mood is: **" + null_check_string(user, 'mood') + "**"
        elif "reset" in args or "clear" in args:
            user.mood = None
            longStr = "**" + author.display_name + "**, your mood has been reset and your autoplaylist has been restored."
        elif args in str(list(self.metaData.keys())):
            user.mood = args
            longStr = "**" + author.display_name + "**, your mood is set to: **" + args + "**"
        else:
            longStr = "Error: We could not find the tag: ", args, "\nTry using \"~tag list\" to see available tags."

        return Response(longStr, delete_after=35)

    async def cmd_heard(self, server, player, channel, author, leftover_args=None):
        """
        Usage:
        {command_prefix}heard #
        {command_prefix}heard max

        Adjusts the amount of songs that need to be played before a previous song can be played again
            # - some number between 0 and your list's size
            max - number of user's songs in autoplaylist

        """
        if not leftover_args:
            prntStr = "__**" + author.display_name + "**__'s heard length is " + str(self.autoplaylist.get_user(author.id).heard_length)
            return Response(prntStr, delete_after=20)

        log.debug(str(leftover_args))
        try:
            if str(leftover_args[0]).isnumeric():
                if int(leftover_args[0]) < 0:
                    prntStr = "Please input a number greater than 0."
                else:
                    user = self.autoplaylist.get_user(author.id)
                    song_list = await self.autoplaylist.get_user_songs(user.user_id)

                    if int(leftover_args[0]) > len(song_list):
                        prntStr = "Unable to change __**" + author.display_name + "**__'s heard length. Desired heard length of *" + leftover_args[0] + "* is larger than song list."
                    else:
                        # check if need to remove some songs
                        #if int(leftover_args[0]) < len(user.heard_list):
                        #    for i in range(0, len(user.heard_list) - int(leftover_args[0])):
                        #        user.heard_list.pop(0)

                        prntStr = "__**" + author.display_name + "**__'s heard length went from *" + str(user.heard_length) + "* to *" + leftover_args[0] + "*"
                        user.heard_length = (int(leftover_args[0]))
            else:
                if leftover_args[0] == "max":
                    user = self.autoplaylist.get_user(author.id)
                    song_list = await self.autoplaylist.get_user_songs(user.user_id)
                    prntStr = "__**" + author.display_name + "**__'s heard length went from *" + str(user.heard_length) + "* to *" + str(len(song_list)) + "*"
                    user.heard_length = (len(song_list))

        except Exception as e:
            prntStr = "Invalid value given. Please input a number."
            log.error(e)
        
        return Response(prntStr, delete_after=20)

    async def cmd_okay(self, author):
        prntStr = [":ok_hand:", author.mention + "'s command was shot down! :gun:", ":skull_crossbones: Deleting List in 10 years. :skull_crossbones:", "Enqueued Doritos Ad to be played. Position in queue: Up Next!", "~smart " + author.mention]
        return Response(random.choice(prntStr), delete_after=20)

    async def cmd_stat(self, server, player, channel, author, leftover_args):
        """
        Usage:
        {command_prefix}stat
        {command_prefix}stat compat

        Prints the number of songs for the top 10 and the author who asked
        Prints the amount of similar songs to the other people in the discord

        """
        
        TOP_COUNT = 10

        if len(leftover_args) > 0:
            if leftover_args[0].strip().lower() == "compat":
                return await self._cmd_compat(server, player, channel, author)
        longStr = ""
        isTopTen = False

        await self.send_typing(channel)

        success, results = await self.autoplaylist.sqlfactory.execute('SELECT u.NAME, COUNT(us.URL) AS c FROM USER_SONG AS us INNER JOIN USER AS u ON u.ID = us.ID GROUP BY us.ID ORDER BY c DESC LIMIT %s', [TOP_COUNT])
        
        if not success:
            log.error('Failed to get top {} users\' song count!'.format(TOP_COUNT))

        longStr += "*--Number of Songs--*\n"
        i = 1
        for user_name, count in results:
            if user_name:
                temp_name = user_name
            else:
                temp_name = ":ghost:"
            tempStr = "{order}. {name}: {count}".format(order=i, name=temp_name, count=count)
            
            # highlight if current user is user that executed command
            if user_name == author.name:
                isTopTen = True
                tempStr = "**__" + tempStr + "__**"
            longStr += tempStr + "\n"
            i += 1

        # printing the users song number
        if not isTopTen:
            success, results = await self.autoplaylist.sqlfactory.execute('SELECT COUNT(URL) FROM USER_SONG WHERE USER_SONG.ID = %s', [author.id])
            if success:
                longStr = "`" + str(author.display_name) + ": " + str(results[0]) + "`\n\n" + longStr
            else:
                log.error('No songs found for user {} but tried to use stat command'.format(str(author)))
                longStr += "`" + str(author) + ": 0`\n\n"

        return Response(longStr, delete_after=35)


    async def _cmd_compat(self, server, player, channel, author):
        #Expended functions on stat
        #   - compat

        t0 = time.clock()
        #If author no music printing
        user = await self.autoplaylist.get_user(author.id)
        if user == None:
            prntStr = "You have no music"
            return Response(prntStr, delete_after=35)

        # Updated #
        prntStr = "**__Affinity to Others__**\n\n"
        similarSongs = {}
        #Goes through each song
        for songObj in self.autoplaylist.songs:
            #If you liked
            likers = await self.autoplaylist.get_likers(songObj.url)
            for liker in likers:
                if liker.user_id in similarSongs.keys():
                    similarSongs[liker.user_id] += 1
                else:
                    similarSongs[liker.user_id] = 1

        song_list = await self.autoplaylist.get_user_songs(user.user_id)
        prntStr += "Total Common Songs: **" + str(sum(similarSongs.values()) - len(song_list)) + "**\n\n"
        #Sort by # of common likes
        similarSongs = sorted(similarSongs.items(), key=lambda x: x[1], reverse=True)
        #Goes through each # of common likes
        for ID_NUM in similarSongs:
            if ID_NUM[0] != author.id:
                temp_person = self._get_user(ID_NUM[0])
                if temp_person != None:
                    prntStr += temp_person.name
                else:
                    prntStr += ":ghost:"
                prntStr += ": *" + str(ID_NUM[1]) + " of " + str(len(song_list)) + "*\n"

        print("Time to process compat: " + str(time.clock() - t0) + " sec")
        return Response(prntStr, delete_after=35)

    async def cmd_ghost(self, player, server, author, channel, permissions, leftover_args):
        """
        Usage:
            {command_prefix}ghost user_name

        MusicBot will act as if the user is in the channel when deciding a song to play.
        Using the command with the user's name twice removes the ghost of the user.

        """
        if len(leftover_args) == 0:
            if author.id not in self.ghost_list.keys():
                prntStr = "You have no ghosts haunting you."
                return Response(prntStr, delete_after=20)
            prntStr = "**" + author.display_name + "**'s haunters: \n"
            for personID in self.ghost_list[author.id]:
                prntStr += "\n:ghost:" + self._get_user(personID).display_name
            return Response(prntStr, delete_after=35)
        user_name = " ".join(leftover_args)
        channel_id_list = list(map(lambda personObj: personObj.id, player.voice_client.channel.voice_members))
        #Check if it was a mention
        if '<@' in user_name and '>' in user_name:
            #Get all the info on the person
            deleteChars = str.maketrans(dict.fromkeys("<@!>"))
            personObj = list(filter(lambda user_list: user_name.translate(deleteChars) == user_list.id, self.get_all_members()))[0]

            #Checking if person is currently in channel
            if str(user_name.translate(deleteChars)) in channel_id_list:
                prntStr = "**" + personObj.display_name + "** is currently in this voice channel."
                return Response(prntStr, delete_after=20)

            #Check if author already has a ghost
            if str(author.id) in self.ghost_list.keys():
                #Check if ghost id already in list (delete if it is in list)
                if str(personObj.id) in self.ghost_list[str(author.id)]:
                    if len(self.ghost_list[str(author.id)]) == 1:
                        del self.ghost_list[str(author.id)]
                    else:
                        self.ghost_list[str(author.id)].remove(str(personObj.id))
                    prntStr = "**" + personObj.display_name + "** was removed from **" + author.display_name + "**'s ghost list"
                    return Response(prntStr, delete_after=20)
                else:
                    self.ghost_list[str(author.id)].append(str(personObj.id))
            else:
                self.ghost_list[str(author.id)] = [str(personObj.id)]
            prntStr = "**" + personObj.display_name + "** was added to **" + author.display_name + "**'s ghost list"
            return Response(prntStr, delete_after=20)
        else:
            #Checking if user_name exists in channel
            for personObj in server.members:
                if user_name.lower() == personObj.display_name.lower() or user_name.lower() == personObj.name.lower() or user_name == personObj.id:
                    #Check if person is in the channel
                    if str(personObj.id) in channel_id_list:
                        prntStr = "**" + personObj.display_name + "** is currently in this voice channel."
                        return Response(prntStr, delete_after=20)

                    #Check if the author already has a ghost list
                    if str(author.id) in self.ghost_list.keys():
                        #Check if ghost name already exists (delete if does)
                        if str(personObj.id) in self.ghost_list[str(author.id)]:
                            if len(self.ghost_list[str(author.id)]) == 1:
                                del self.ghost_list[str(author.id)]
                            else:
                                self.ghost_list[str(author.id)].remove(str(personObj.id))
                            prntStr = "**" + personObj.display_name + "** was removed from **" + author.display_name + "**'s ghost list"
                            return Response(prntStr, delete_after=20)
                        else:
                            self.ghost_list[str(author.id)].append(str(personObj.id))
                    #If doesn't create new list
                    else:
                        self.ghost_list[str(author.id)] = [str(personObj.id)]
                    prntStr = "**" + personObj.display_name + "** was added to **" + author.display_name + "**'s ghost list"
                    return Response(prntStr, delete_after=20)
        prntStr = "**" + user_name + "** does not exist in this Discord"
        return Response(prntStr, delete_after=20)

    def get_ghost_exist(self, id):
        if str(id) in self.ghost_list.keys():
            return self.ghost_list[str(id)]
        else:
            return []


    async def cmd_tag(self, player, author, channel, permissions, leftover_args=None):
        """
        Usage:
            {command_prefix}tag [command] [url(OPTIONAL)] the_tag

        Ex: ~tag add rock
        [command]:
        - ADD : Adds the current song to the specified tag
        - REMOVE : Removes the current song from the specified tag
        - PLAY : Plays a random song from the specified tag
        - LIST : Prints all the tags
        - SHOW : Shows the songs in the specified tag
        - MSG : Messages user with all the songs w/ urls of the specified tag
        - REPLACE :  [tag1] [tag2] replacing tag1 with tag2
        """

        await self.send_typing(channel)
        if len(leftover_args) >= 1:
            self.updateMetaData()
            if leftover_args[0].lower() == "list":
                return await self._cmd_listtag(player, author, channel)
            elif leftover_args[0].lower() == "show":
                tag = ' '.join(leftover_args[1:])
                return await self._cmd_showtag(player, author, channel, permissions, tag)
            elif leftover_args[0].lower() == "msg":
                tag = ' '.join(leftover_args[1:])
                return await self._cmd_msgtag(player, author, channel, permissions, tag)
            elif leftover_args[0].lower() == "play":
                tag = ' '.join(leftover_args[1:])
                return await self._cmd_playtag(player, author, channel, permissions, tag)
            elif leftover_args[0].lower() == "replace":
                tags = " ".join(leftover_args[1:])
                if tags != "":
                    if (tags[0] == '[' and ']' in tags[1:-1]) and ('[' in tags[1:-1] and tags[-1] == ']') and (tags[1:-1].find(']') < tags[1:-1].find('[')):
                        tag1 = tags[1:tags[1:-1].find(']') + 1]
                        tag2 = tags[tags[1:-1].find('[') + 2:-1]
                        return await self._cmd_replacetag(author, tag1, tag2)
                prntStr = "Please put the command of replace in the form of `" + self.config.command_prefix + "tag replace [tag_initial] [tag_final]`, and include the brackets."
                return Response(prntStr, delete_after=20)

            if "http" in leftover_args[1] and "://" in leftover_args[1] or "www." in leftover_args[1]:
                song_info = await self.autoplaylist.find_song_by_url(leftover_args[1])
                tag = ' '.join(leftover_args[2:])
                if song_info == None:
                    prntStr = "**" + leftover_args[1] + "** is not added in the Autoplay list"
                    return Response(prntStr, delete_after=20)
            else:
                if not player.is_playing:
                    prntStr = "Error: No song is playing"
                    return Response(prntStr, delete_after=20)
                song_info = await self.autoplaylist.find_song_by_url(player.current_entry.url)
                tag = ' '.join(leftover_args[1:])
                if song_info == None:
                    prntStr = "**" + player.current_entry.title + "** is not added in the Autoplay list"
                    return Response(prntStr, delete_after=20)

            if leftover_args[0].lower() == "add":
                return await self._cmd_addtag(player, author, channel, tag, song_info)
            elif leftover_args[0].lower() == "remove":
                return await self._cmd_removetag(player, author, channel, tag, song_info)
            else:
                prntStr = "**[" + leftover_args[0] + "]** is not a recognized command"
                return Response(prntStr, delete_after=20)
        else:
            prntStr = "**" + str(len(leftover_args)) + "** arguments were given **2 or more** arguments expected"
            return Response(prntStr, delete_after=20)


    async def _cmd_addtag(self, player, author, channel, tag, song=None):
        """
        Usage:
            {command_prefix}addtag TAG

        Adds the playing song to the specified tag
        """
        log.debug("Trying to add " + null_check_string(song, 'title') + " to " + tag + " tag")

        if song == None:
            prntStr = "No song was playing during **[add]** command"
            return Response(prntStr, delete_after=20)

        if tag == "reset" or tag == "clear":
            prntStr = "Sorry, '**reset**' and '**clear**' are reserved tags. Please choose something else"
            return Response(prntStr, delete_after=20)

        #Checks if tag already exists
        if tag in self.metaData.keys():
            #Checks if the song is already in the tag/list
            if song.url not in self.metaData[tag]:
                self.metaData[tag].append(song.url)
            else:
                prntStr = "**" + null_check_string(song, 'title') + "** is already added to the **[" + tag + "]** tag"
                return Response(prntStr, delete_after=20)
        else:
            #If tag doesn't exist, create a new tag
            self.metaData[tag] = [song.url]
        #Updating list to file
        self._cmd_updatetags()
        await self.tag_update_apl(tag, song, 'add')
        prntStr = "**" + null_check_string(song, 'title') + "** was added to the **[" + tag + "]** tag"
        return Response(prntStr, delete_after=20)

    async def _cmd_removetag(self, player, author, channel, tag, song=None, printing=True):
        """
        Usage:
            {command_prefix}removetag TAG

        Removes the current playing song for the specified tag
        """

        # Checks if the tag exists first
        if tag in self.metaData.keys():
            #Checks if the url is in the list
            if song.url in self.metaData[tag]:
                self.metaData[tag].remove(song.url)
                #Remove tag entirely if empty
                if len(self.metaData[tag]) == 0:
                    del self.metaData[tag]
                #Update tags file
                self._cmd_updatetags()
                await self.tag_update_apl(tag, song, 'remove')
                prntStr = "**" + null_check_string(song, 'title') + "** is removed from **[" + tag + "]** tag"
            else:
                prntStr = "**" + null_check_string(song, 'title') + "** was not in **[" + tag + "]** tag"

        if printing == True:
            return Response(prntStr, delete_after=20)
        else:
            return True

    async def _cmd_playtag(self, player, author, channel, permissions, tag):
        """
        Usage:
            {command_prefix}playtag TAG

        Plays a song from the specified tag
        """

        #Checks if tag exists
        if tag in self.metaData.keys():
            playUrl = random.choice(self.metaData[tag])
        else:
            prntStr = "The tag **[" + tag + "]** does not exist."
            return Response(prntStr, delete_after=35)
        try:
            info = await self.downloader.extract_info(player.playlist.loop, player.current_entry.url, download=False, process=False)
            if not info:
                raise exceptions.CommandError("That video cannot be played.", expire_in=30)
            entry, position = await self._add_entry(player=player, song_url=playUrl, channel=channel, author=author)
            if position == 1 and player.is_stopped:
                position = 'Up next!'
            else:
                try:
                    time_until = await player.playlist.estimate_time_until(position, player)
                except:
                    time_until = ''
            #Not sure if needed
            #await entry.get_ready_future()
            prntStr = "Enqueued **%s** to be played. Position in queue: %s - estimated time until playing: %s" %(entry.title, position, time_until)
            return Response(prntStr, delete_after=30)
        except Exception:
            prntStr = "A song from **[" + tag + "]** was unable to be added."
            return Response(prntStr, delete_after=35)

    async def _cmd_listtag(self, player, author, channel):
        """
        Usage:
            {command_prefix}listtag

        Shows all the tags
        """

        #await self.send_typing(channel)
        prntStr = "__List of all tags__\n\n"
        #Will sort the metaData by the number of songs in it largest at top
        #for key,value in sorted(self.metaData.items(), key=lambda tuple: (len(tuple[1]),tuple[0]), reverse=True):
        #Will sort the metaData by the
        for key,value in sorted(self.metaData.items(), key=lambda set : set[0].lower()):
            if len(prntStr + key) < 1990:
                prntStr += "**[" + key + "]** : " + str(len(value)) + "\n"
            else:
                await self.safe_send_message(channel, prntStr, expire_in=30)
                await self.send_typing(channel)
                prntStr = ""
        return Response(prntStr, delete_after=30)

    async def _cmd_showtag(self, player, author, channel, permissions, tag):
        """
        Usage:
            {command_prefix}showtag TAG

        Shows the songs in a tag
        """

        #Checks if tag exists
        if tag in self.metaData.keys():
            #playUrl = random.choice(self.metaData[tag])
            pass
        else:
            prntStr = "The tag **[" + tag + "]** does not exist."
            return Response(prntStr, delete_after=35)

        prntStr = "__Songs in **[" + tag.capitalize() + "]** tag__\n\n"

        for link in self.metaData[tag]:
            song = await self.autoplaylist.find_song_by_url(link)
            if song == None:
                continue
            if len(prntStr + str(song)) > 2000:
                Response(prntStr, delete_after=50)
                prntStr = ""
            if song.title:
                prntStr += ":notes:" + song.title + "\n"
            else:
                prntStr += ":notes:" + "[NO TITLE] <" + song.url + ">\n"

        return Response(prntStr, delete_after=50)

    async def _cmd_msgtag(self, player, author, channel, permissions, tag):
        """
        Usage:
            {command_prefix}msgtag the_tag

        Messages all the songs and urls in a tag
        """

        #Checks if tag exists
        if tag in self.metaData.keys():
            pass
        else:
            prntStr = "The tag **[" + tag + "]** does not exist."
            return Response(prntStr, delete_after=35)

        prntStr = []
        for link in self.metaData[tag]:
            song = await self.autoplaylist.find_song_by_url(link)
            
            if song == None:
                continue
            prntStr.append(null_check_string(song, 'title') + "\r\n\t" + link)

        with BytesIO() as prntDoc:
            prntDoc.writelines(d.encode('utf8') + b'\n' for d in prntStr)
            prntDoc.seek(0)
            await self.send_file(author, prntDoc, filename='%s_tagList.txt' %tag)

        return Response(":mailbox_with_mail:", delete_after=20)

    async def _cmd_replacetag(self, author, tag1, tag2):
        if tag1 in self.metaData.keys():
            print(list(map(lambda song_url : song_url , self.metaData[tag1])))
            if author.id in list(map(lambda song_url : self.autoplaylist.get_likers(song_url), self.metaData[tag1])):
                return Response("Woah buckaroo", delete_after=20)
            self.metaData[tag2] = self.metaData.pop(tag1)
            self._cmd_updatetags()
            await self.tag_update_apl([tag1, tag2], None, 'replace')
            prntStr = "The tag **[" + tag1 + "]** was replaced with the tag **[" + tag2 + "]**"
        else:
            prntStr = "The tag **[" + tag1 + "]** does not exist."
        return Response(prntStr, delete_after=20)

    def _cmd_updatetags(self):
        """
        Usage:
            self._cmd_updatetags()

        Takes the current metaData dictionary and pushes to file
        """

        str_to_write = []
        for metaTag in self.metaData:
            #First tag
            str_to_write.append(metaTag)
            #Second push urls
            str_to_write.append(self.metaData[metaTag])
        # print(str_to_write)
        write_file(self.config.metadata_file, str_to_write)

    async def tag_update_apl(self, tag, song, cmd):
        if cmd == 'add':
            #Changing song in APL
            song.add_tag(tag)
        elif cmd == 'remove':
            #Changing song in APL
            song.remove_tag(tag)
        elif cmd == 'replace':
            #Changing song in APL
            for song_url in self.metaData[tag[1]]:
                song = await self.autoplaylist.find_song_by_url(song_url)
                if song:
                    song.remove_tag(tag[0])
                    song.add_tag(tag[1])
                
                #OUTDATED since url in User's list
                # #Changing song in User's list
                # song_likers = song.getLikers()
                # for user_id in song_likers:
                #     users_Song = await self.autoplaylist.get_user(user_id).getSong(song)
                #     users_Song.removeTag(tag[0])
                #     users_Song.addTag(tag[1])

    # bootstrap for add entry
    async def _add_entry(self, player, song_url, **meta):

        people = [m for m in player.voice_client.channel.voice_members if not (m.deaf or m.self_deaf or m.id == self.user.id)]
    
        results = await self.autoplaylist.sqlfactory.song_read(song_url)
        
        global_song = None

        if results and len(results) == 1:
            url, title, play_count, volume, updt_dt_tm, cret_dt_tm = results[0]
            volume = str(volume)
            global_song = Song(url, title, play_count, volume, updt_dt_tm, cret_dt_tm)
        else:
            log.warning('[_ADD_ENTRY] First time playing {}, adding to Song table and liking it for user {}'.format(song_url, meta.get('author', 'No Author')))
            #if not await self.autoplaylist.user_like_song(meta.get('author', None), song_url):
            #    log.error('[_ADD_ENTRY] Failed to create song {} for user {}'.format(song_url, meta.get('author', 'No Author')))

        last_played = global_song.updt_dt_tm if global_song else None

        # updating playcount for users in channel
        for each_discord_user in people:
            each_user = await self.autoplaylist.get_user(each_discord_user)
            if each_user:
                results = await self.autoplaylist.sqlfactory.user_song_read(each_user.user_id, song_url)
                if results:
                    _id, _url, _play_count, _last_played_dt_tm = results
                    if not await self.autoplaylist.sqlfactory.user_song_update(_id, _url, int(_play_count)+1, get_cur_dt_tm(), _id, _url):
                        log.error('[_ADD_ENTRY] Failed to update user_song for user {} and song {}'.format(str(each_user), str(global_song)))
                else:
                    log.warning('[_ADD_ENTRY] User {} doesn\'t like this song {}'.format(each_user, global_song))
                    log.warning('[_ADD_ENTRY] Results {}'.format(str(results)))

                    
        # updating global playcount
        if global_song and not await self.autoplaylist.sqlfactory.song_update(global_song.url, global_song.title, global_song.play_count+1, global_song.volume, get_cur_dt_tm(), global_song.cret_dt_tm, global_song.url):
            log.error('[ON_PLAYER_FINISHED_PLAYING] Failed to update song for song {}'.format(global_song))

        return await player.playlist.add_entry(song_url=global_song.url if global_song else song_url, channel=meta.get('channel', None), author=meta.get('author', None), last_played=last_played)

    def remove_song_from_tags(self, song):
        print("Looking for: " + song.url)
        updated_tags = False
        future_delete = []
        for tag_key in self.metaData.keys():
            if song.url in self.metaData[tag_key]:
                self.metaData[tag_key].remove(song.url)
                if len(self.metaData[tag_key]) == 0:
                    future_delete.append(tag_key)
                updated_tags = True
        for delete_tag in future_delete:
            del self.metaData[delete_tag]
        if updated_tags == True:
            self._cmd_updatetags()

    def cleanup_tags(self):
        for key, values in sorted(self.metaData.items()):
            self.metaData[key] = list(filter(lambda url : self.autoplaylist._find_song_by_url(url) != None, values))
        print("Deleting Tags: " + str(", ".join(list(filter(lambda tag : len(self.metaData[tag]) == 0, self.metaData)))))
        for delete_tag in list(filter(lambda tag : len(self.metaData[tag]) == 0, self.metaData)):
            del self.metaData[delete_tag]
        self._cmd_updatetags()

    async def cmd_embed(self, player, author, channel, permissions, leftover_args):
        em = discord.Embed(type="rich")
        # leftover_args = list(map(lambda ele : int(ele), leftover_args))
        #chars = ('0123456789'  * 7 + '\n') * 30
        #title = 256 Char limit
        #description = 2048 Char limit
        #field.name = 256 char limit
        #field.value = 1024 char limit
        # em.title = chars[:leftover_args[0]]

        em.title = leftover_args[0]
        try:
            em.description = leftover_args[1]
        except:
            log.error("Description failed")
        try:
            em.add_field(name=leftover_args[2], value=leftover_args[3])
            # em.add_field(name=chars[:leftover_args[2]], value=chars[:leftover_args[3]], inline=True)
        except:
            log.error("set_field failed")
        await self.send_message(channel, embed=em)

    async def cmd_listhas(self, player, author, channel, permissions, leftover_args):
        """
        Usage:
            {command_prefix}listhas songTitle

        Looks if a song title is in your or others lists

        """

        prntStr = ""
        if len(leftover_args) == 0:
            prntStr += "```Usage:\n\t{command_prefix}listhas songTitle\n\nLooks if a song title in in your list```"
            return Response(prntStr, delete_after=20)
        else:
            thinkingMsg = await self.safe_send_message(channel, "Processing:thought_balloon:")
            messages = []
            title = '**Autoplay lists containing: ' + ' '.join(leftover_args) +  '**'
            if len(title) > 256:
                title = 'Autoplay Lists'

            ContainsList = []                        
            ContainsList = list(filter(lambda each_song: each_song, self.autoplaylist._find_songs_by_title(" ".join(leftover_args))))

            #sorting into a list for each person who liked the songs
            peopleListSongs = {}
            for songObj in ContainsList:
                print(str(songObj))
                for person in await self.autoplaylist.get_likers(songObj.url):
                    if person.user_id not in peopleListSongs.keys():
                        peopleListSongs[person.user_id] = [songObj]
                    else:
                        peopleListSongs[person.user_id].append(songObj)

            if len(peopleListSongs) == 0:
                await self.safe_delete_message(thinkingMsg)
                prntStr = "No song has **__" + " ".join(leftover_args).strip() + "__** in the title"
                return Response(prntStr, delete_after=20)

            t0 = time.perf_counter()
            #Printing: Yours
            if author.id in peopleListSongs:
                messages.append(await self._embed_listhas(channel, author, peopleListSongs[author.id], title, 0xffb900))
                del peopleListSongs[author.id]
                title = None
            print("2nd run: " + str(time.perf_counter() - t0))

            #Printing: Others
            for author_id in peopleListSongs.keys():
                member = self._get_user(author_id)
                if member != None: #Unknown User
                    messages.append(await self._embed_listhas(channel, member, peopleListSongs[author_id], title))
                    title = None

            await self.safe_delete_message(thinkingMsg)
            messages.append(await self.send_message(channel, "```Finished Printing```"))
            asyncio.ensure_future(self._wait_delete_msgs(messages, 20 + (len(messages) * 5)))


            # em1 = discord.Embed(type="rich")
            # em1.title = title
            # # em1.description = em_prsnPrint
            # em1.set_footer(text=(author.display_name + "    | 1 of 3 pages" ))
            # # em1.add_field(name="1 of 3 pages", value=em_prsnPrint)
            # print(em1.fields)
            # msgr = await self.send_message(channel, embed=em1)
            # #other option self.emojis.find("name", name)
            # await self.add_reaction(msgr, "◀") #:arrow_backward:
            # # await self.add_reaction(msgr, ":arrow_backward:")
            # await self.add_reaction(msgr, "▶") #:arrow_forward:
    
    async def _embed_listhas(self, channel, userName, songList, title=None, color=0x006600):
        #Right now will be one embed per person
        em = discord.Embed(title=title, type="rich", color=color)
        EM_CHAR_LIMIT = 6000
        FIELDS_LIMIT = 25
        prntStr = ""
        
        em.description = "\t:busts_in_silhouette:__" + userName.display_name + "__\n"
        em.set_footer(text=userName.name)
        char_cnt = len(em.description + em.footer.text)
        
        for songObj in songList:
            lnprnt = ":point_right:[" + null_check_string(songObj, 'title') + "](" + self.check_url(songObj.url) + ")\n"
            if (char_cnt + len(prntStr)) > (EM_CHAR_LIMIT - 15) or len(em.fields) == FIELDS_LIMIT:
                em.set_footer(text=userName.name + " | Partial List")
                # em.set_field_at(-1, name=em.fields[-1].name + " | Partial List", value=em.fields[-1].value, inline=True)
                break

            if len(em.description + lnprnt) < 2048:
                em.description += lnprnt
                char_cnt += len(lnprnt)
            elif len(prntStr + lnprnt) > 1024:
                em.add_field(name="\u200b",value=prntStr, inline=True)
                char_cnt += len(em.fields[-1].name + em.fields[-1].value)
                log.debug("Field ["  + str(len(em.fields)) + "]: " + str(len(prntStr)) + " of " + str(char_cnt))
                prntStr = lnprnt
            else:
                prntStr += lnprnt
                lnprnt = ""
        # print(em.fields)

        if len(em.fields) < FIELDS_LIMIT and (char_cnt + len(prntStr)) < EM_CHAR_LIMIT and lnprnt == "":
            # log.debug(userName + " : " + prntStr)
            em.add_field(name='\u200b', value=prntStr, inline=True)

        return await self.send_message(channel, embed=em)

    async def cmd_oldlisthas(self, player, author, channel, permissions, leftover_args):
        ###### 1/10/2018 ######
        #Add to list after whole list is compiled
        thinkingMsg = await self.safe_send_message(channel, "Processing:thought_balloon:")
        prntStr = ""
        songsInList = 0

        if len(leftover_args) == 0:
            prntStr += "```Usage:\n\t{command_prefix}listhas songTitle\n\nLooks if a song title in in your list```"
        else:
            t0 = time.clock()
            #IMOPRTANT: .strip().lower()
            #finds all songs with the containing words
            ContainsList = await self.find_songs_by_title(leftover_args)
            songsInList = len(ContainsList)
            peopleListSongs = {}
            #sorting into a list for each person who liked the songs
            for songObj in ContainsList:
                for person in await self.autoplaylist.get_likers(songObj.url):
                    if person not in peopleListSongs:
                        peopleListSongs[person] = [songObj]
                    else:
                        peopleListSongs[person].append(songObj)

            prntStr = '**Autoplay lists containing: "' + ' '.join(leftover_args) +  '"**'

            #Check if the 'command' asker has songs
            if author.id in peopleListSongs:
                em_prsnPrint = "\n\t:busts_in_silhouette:__Yours__\n"
                prsnPrint = "\n\t:busts_in_silhouette:__Yours__\n"
                for songObj in peopleListSongs[author.id]:
                    prsnPrint += ":point_right:" + null_check_string(songObj, 'title') + "(<" + songObj.url + ">)" + "\n"
                    em_prsnPrint += ":point_right:[" + null_check_string(songObj, 'title') + "](" + songObj.url + ")" + "\n"
                #Correcting for too many songs
                if len(prntStr + prsnPrint) > DISCORD_MSG_CHAR_LIMIT:
                    prsnPrint = "```Partial List - Yours```" + prsnPrint[33:]
                    cut_index = prsnPrint[:DISCORD_MSG_CHAR_LIMIT - len(prntStr)].rfind('\n')
                    #print("Cut at: " + str(cut_index) + " of " + str(len(prntStr + prsnPrint)))
                    prsnPrint = prsnPrint[:cut_index]
                    prntStr += prsnPrint
                    await self.send_typing(channel)
                    await self.safe_send_message(channel, prntStr, expire_in=(songsInList + 60))
                    prntStr = ""
                else:
                    prntStr += prsnPrint
            #Goes through every other persons list
            for person in peopleListSongs.keys():
                if person == author.id:
                    continue
                userName = "Unknown User" if self._get_user(person) == None else self._get_user(person).name
                em_prsnPrint = "\n\t:busts_in_silhouette:__" + userName + "__\n"
                prsnPrint = "\n\t:busts_in_silhouette:__" + userName + "__\n"
                for songObj in peopleListSongs[person]:
                    prsnPrint += ":point_right:" + null_check_string(songObj, 'title') + "(<" + songObj.url + ">)" + "\n"
                    em_prsnPrint += ":point_right:[" + null_check_string(songObj, 'title') + "](" + songObj.url + ")" + "\n"
                #Correcting for too many songs (sqrewing over ppl b/c i'm lazy)
                if len(prntStr + prsnPrint) > DISCORD_MSG_CHAR_LIMIT:
                    prsnPrint = "\n```Partial List - " + userName + "```" + prsnPrint[27+len(userName):]
                    cut_index = prsnPrint[:DISCORD_MSG_CHAR_LIMIT - len(prntStr)].rfind('\n')
                    #Check if the holding print statment (prntStr) is close to the max limit and
                    #   doesn't give space to next list
                    if cut_index == -1:
                        await self.send_typing(channel)
                        await self.safe_send_message(channel, prntStr, expire_in=(songsInList + 60))
                        prntStr = ""
                        cut_index = prsnPrint[:DISCORD_MSG_CHAR_LIMIT].rfind('\n')
                    print("Cut at: " + str(cut_index) + " of " + str(len(prntStr + prsnPrint)))
                    prsnPrint = prsnPrint[:cut_index]
                    prntStr += prsnPrint
                    await self.send_typing(channel)
                    await self.safe_send_message(channel, prntStr, expire_in=(songsInList + 60))
                    prntStr = ""
                else:
                    prntStr += prsnPrint
            #Note: this does once finished, the old timer did till parsed
            print("Time pass on your list: %s", time.clock() - t0)
            # print(len(prntStr))
            await self.safe_delete_message(thinkingMsg)
            if len(prntStr) != 0:
                return Response(prntStr, delete_after=50)
            return

    async def cmd_mylist(self, player, channel, author, permissions, leftover_args):
        """
        Usage:
            {command_prefix}mylist

        View the songs in your personal autoplaylist.
        """

        data = []

        user = await self.autoplaylist.get_user(author.id)
        if user:

            song_list = await self.autoplaylist.get_user_songs(user.user_id)
            if len(song_list) == 0:
                data.append("Your auto playlist is empty.")
            else:
                # song_list = list(map(lambda key: self._url_to_song_[key], song_list))

                sorted_songs = sorted(song_list, key=lambda song: song.title.lower() if song.title else "")
                for song in sorted_songs:
                    if song:
                        data.append(str(song) + ", Playcount: " + str(song.play_count) + "\r\n")
                    else:
                        log.warning("[MYLIST] Null song")

            with BytesIO() as sdata:
                sdata.writelines(d.encode('utf8') for d in data)
                sdata.seek(0)

                # TODO: Fix naming (Discord20API-ids.txt)
                await self.send_file(author, sdata, filename='%s-autoplaylist.txt' % (author))

        return Response(":mailbox_with_mail:", delete_after=20)

    async def cmd_mylist2(self, player, channel, author, permissions, leftover_args):
        """
        Usage:
            {command_prefix}mylist

        View the songs in your personal autoplaylist.
        """

        data = []

        user = await self.autoplaylist.get_user(author.id)
        if user:

            song_list = await self.autoplaylist.get_user_songs(user.user_id)
            if len(song_list) == 0:
                data.append("Your auto playlist is empty.")
            else:
                sorted_songs = sorted(song_list, key=lambda song: song.title.lower() if song.title else "")
                for song in sorted_songs:
                    if song:
                        data.append(str(song) + ", Playcount: " + str(song.play_count) + "\r\n")
                    else:
                        log.warning("[MYLIST2] Null song")

            with BytesIO() as sdata:
                sdata.writelines(d.encode('utf8') for d in data)
                sdata.seek(0)

                # TODO: Fix naming (Discord20API-ids.txt)
                await self.send_file(author, sdata, filename='%s-autoplaylist.txt' % (author))

        return Response(":mailbox_with_mail:", delete_after=20)

    async def cmd_like(self, player, channel, author, permissions, leftover_args):
        """
        Usage:
            {command_prefix}like

        Adds the current song to your autoplaylist.
        """

        await self.send_typing(channel)

        reply_text = ""
        user = ""

        if leftover_args:
            song_url = ''.join(leftover_args)
        else:
            song_url = None

        if song_url == "last" or song_url == "end":
            song_url = -1

        if song_url is None:
            if player.current_entry:
                url = player.current_entry.url
                title = player.current_entry.title
            else:
                log.warning("Can't like a song while the player isn't playing")
                return Response("ERROR: Can't like a song while the player isn't playing", delete_after=30)
        else:
            song_url = self.check_url(song_url)
            url = song_url
            cached_song = await self.autoplaylist.find_song_by_url(url)
            if cached_song:
                title = null_check_string(cached_song, 'title')
            else:
                title = None

        if await self.autoplaylist.user_like_song(author.id, url, title):
            reply_text = "**%s**, the song **%s** has been added to your auto playlist."
        else:
            reply_text = "**%s**, this song **%s** is already added to your auto playlist or something went wrong."

        user = str(author)
        if title == None:
            title = url

        reply_text %= (user, title)

        return Response(reply_text, delete_after=30)

    async def cmd_dislike(self, player, channel, author, permissions, leftover_args):
        """
        Usage:
            {command_prefix}dislike
            {command_prefix}dislike song_url
            {command_prefix}dislike queue_position

        Removes the current song from your autoplaylist.
        """

        await self.send_typing(channel)

        reply_text = ""
        user = ""

        if leftover_args:
            song_url = ' '.join([*leftover_args])
        else:
            song_url = None

        if song_url == "last" or song_url == "end":
            song_url = -1

        try: 
            song_url = int(song_url)
        except:
            pass

        if not song_url:
            if player.current_entry:
                url = player.current_entry.url
                title = player.current_entry.title
            else:
                log.warning("Can't dislike a song while the player isn't playing")
                return Response("ERROR: Can't dislike a song while the player isn't playing", delete_after=30)
        elif type(song_url) == int:
            position = int(song_url)
            entry = await player.playlist.get_entry(position)

            if entry:
                url = entry.url
                title = entry.title
            else:
                url = player.current_entry.url
                title = player.current_entry.url
        else:
            song_url = self.check_url(song_url)
            url = song_url
            cached_song = await self.autoplaylist.find_song_by_url(url)
            if cached_song:
                title = cached_song.title
            else:
                title = None

        if await self.autoplaylist.user_dislike_song(author.id, url, title):
            reply_text = "**%s**, the song **%s** has been removed from your auto playlist."
            if player.current_entry:
                if player.current_entry.url:
                    if player.current_entry.url == url:
                        player.current_entry.disliked = True
        else:
            reply_text = "**%s**, the song **%s** wasn't in your auto playlist or something went wrong."

        user = str(author)

        if title is None:
            if player.current_entry.url:
                if player.current_entry.url == url:
                    title = player.current_entry.title
                else:
                    title = url

        reply_text %= (user, title)

        return Response(reply_text, delete_after=30)

    async def cmd_remove(self, player, channel, author, permissions, position):
        """
        Usage:
            {command_prefix}remove position
            {command_prefix}remove -1
            {command_prefix}remove last
            {command_prefix}remove end

        Removes the song from the playlist. Removing by text is coming soon.
        """

        if position == "last" or position == "end":
            position = -1

        # Check for popping from empty queue
        if len(player.playlist.entries) == 0:
            reply_text = "[Error] Queue is empty."
            return Response(reply_text, delete_after=30)

        try:
            position = int(position)
        except ValueError:
            reply_text = "[Error] Invalid position in queue. Enter a valid integer between 1 and %s."
            reply_text %= len(player.playlist.entries)
            return Response(reply_text, delete_after=30)

        # Validating
        if position == 1:
            entry = player.playlist.remove_first()
        elif (position < 1 or position > len(player.playlist.entries)) and position != -1:
            reply_text = "[Error] Invalid ID. Available positions are between 1 and %s."
            reply_text %= len(player.playlist.entries)
            return Response(reply_text, delete_after=30)
        else:
            entry = await player.playlist.remove_entry(position, channel=channel, author=author)

        reply_text = "Removed **%s** from the queue. It was in position: %s"
        btext = entry.title

        if position == -1:
            position = len(player.playlist.entries) + 1

        reply_text %= (btext, position)

        return Response(reply_text, delete_after=30)

    async def cmd_play(self, player, channel, author, permissions, leftover_args, song_url):
        """
        Usage:
            {command_prefix}play song_url
            {command_prefix}play text to search for

        Adds the song to the playlist.  If a link is not provided, the first
        result from a youtube search is added to the queue.
        """

        await self.send_typing(channel)

        song_url = song_url.strip('<>')

        if permissions.max_songs and player.playlist.count_for_user(author) >= permissions.max_songs:
            raise exceptions.PermissionsError(
                "You have reached your enqueued song limit (%s)" % permissions.max_songs, expire_in=30
            )

        await self.send_typing(channel)

        if leftover_args:
            song_url = ' '.join([song_url, *leftover_args])

        # Not sure how else to do this since on_message is so picky about filling all tail-end params
        if song_url.split(' ')[-1] == "True":
            immediate = True
            song_url = song_url.replace(" True", "")
        else:
            immediate = False

        # let's see if we already have this song or a similar one. i feel like this will help 70% of the time
        # let's check the songs the user likes before looking at other people's

        song_url = self.check_url(song_url)

        song = await self.autoplaylist.find_song_by_url(song_url)
        if song:
            song_url = song.url

        try:
            info = await self.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
        except Exception as e:
            raise exceptions.CommandError(e, expire_in=30)

        if not info:
            raise exceptions.CommandError(
                "That video cannot be played.  Try using the {}stream command.".format(self.config.command_prefix),
                expire_in=30
            )

        # abstract the search handling away from the user
        # our ytdl options allow us to use search strings as input urls
        if info.get('url', '').startswith('ytsearch'):
            #log.debug("[Command:play] Searching for \"%s\"" % song_url)
            info = await self.downloader.extract_info(
                player.playlist.loop,
                song_url,
                download=False,
                process=True,    # ASYNC LAMBDAS WHEN
                on_error=lambda e: asyncio.ensure_future(
                    self.safe_send_message(channel, "```\n%s\n```" % e, expire_in=120), loop=self.loop),
                retry_on_error=True
            )

            if not info:
                raise exceptions.CommandError(
                    "Error extracting info from search string, youtubedl returned no data.  "
                    "You may need to restart the bot if this continues to happen.", expire_in=30
                )

            if not all(info.get('entries', [])):
                # empty list, no data
                log.debug("Got empty list, no data")
                return

            # TODO: handle 'webpage_url' being 'ytsearch:...' or extractor type
            song_url = info['entries'][0]['webpage_url']
            info = await self.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
            # Now I could just do: return await self.cmd_play(player, channel, author, song_url)
            # But this is probably fine

        # TODO: Possibly add another check here to see about things like the bandcamp issue
        # TODO: Where ytdl gets the generic extractor version with no processing, but finds two different urls

        if not 'entries' in info:
            # not playlist
            if permissions.max_song_length and info.get('duration', 0) > permissions.max_song_length:
                raise exceptions.PermissionsError(
                    "Song duration exceeds limit (%s > %s)" % (info['duration'], permissions.max_song_length),
                    expire_in=30
                )

            try:
                entry, position = await self._add_entry(player=player, song_url=song_url, channel=channel, author=author)
                if immediate == True:
                    if len(player.playlist) > 1:
                        player.playlist.promote_last()
                        position = 1
                    if player.is_playing:
                        player.skip()

            except exceptions.WrongEntryTypeError as e:
                if e.use_url == song_url:
                    log.warning("Determined incorrect entry type, but suggested url is the same. Help.")

                log.debug("Assumed url \"%s\" was a single entry, was actually a playlist" % song_url)
                log.debug("Using \"%s\" instead" % e.use_url)

                return await self.cmd_play(player, channel, author, permissions, leftover_args, e.use_url)

            reply_text = "Enqueued **%s** to be played. Position in queue: %s"
            btext = entry.title            
        else:            
            self.email_util.send_exception(author.display_name, entry.url, "User tried to play a playlist")

        if position == 1:
            position = 'Up next!'
            reply_text %= (btext, position)

        else:
            try:
                time_until = await player.playlist.estimate_time_until(position, player)
                reply_text += ' - estimated time until playing: %s'
            except:
                traceback.print_exc()
                time_until = ''

            reply_text %= (btext, position, ftimedelta(time_until))

        try:
            log.info("[PLAY] " + author.display_name + ": " + entry.title)
            await self.autoplaylist.user_like_song(author.id, entry.url, entry.title, 0, 0.15)            
        except Exception as e:
            log.error("Failed to add song to apl in play command " + entry.title)
            log.error("ERR: " + str(e))
            self.email_util.send_exception(author.display_name, entry.title, "Failed to add song to apl in play command")

        return Response(reply_text, delete_after=30)

    async def _cmd_play_playlist_async(self, player, channel, author, permissions, playlist_url, extractor_type):
        """
        Secret handler to use the async wizardry to make playlist queuing non-"blocking"
        """

        await self.send_typing(channel)
        info = await self.downloader.extract_info(player.playlist.loop, playlist_url, download=False, process=False)

        if not info:
            raise exceptions.CommandError("That playlist cannot be played.")

        num_songs = sum(1 for _ in info['entries'])
        t0 = time.time()

        busymsg = await self.safe_send_message(
            channel, "Processing %s songs..." % num_songs)  # TODO: From playlist_title
        await self.send_typing(channel)

        entries_added = 0
        if extractor_type == 'youtube:playlist':
            try:
                entries_added = await player.playlist.async_process_youtube_playlist(
                    playlist_url, channel=channel, author=author)
                # TODO: Add hook to be called after each song
                # TODO: Add permissions

            except Exception:
                log.error("Error processing playlist", exc_info=True)
                raise exceptions.CommandError('Error handling playlist %s queuing.' % playlist_url, expire_in=30)

        elif extractor_type.lower() in ['soundcloud:set', 'bandcamp:album']:
            try:
                entries_added = await player.playlist.async_process_sc_bc_playlist(
                    playlist_url, channel=channel, author=author)
                # TODO: Add hook to be called after each song
                # TODO: Add permissions

            except Exception:
                log.error("Error processing playlist", exc_info=True)
                raise exceptions.CommandError('Error handling playlist %s queuing.' % playlist_url, expire_in=30)


        songs_processed = len(entries_added)
        drop_count = 0
        skipped = False

        if permissions.max_song_length:
            for e in entries_added.copy():
                if e.duration > permissions.max_song_length:
                    try:
                        player.playlist.entries.remove(e)
                        entries_added.remove(e)
                        drop_count += 1
                    except:
                        pass

            if drop_count:
                log.debug("Dropped %s songs" % drop_count)

            if player.current_entry and player.current_entry.duration > permissions.max_song_length:
                await self.safe_delete_message(self.server_specific_data[channel.server]['last_np_msg'])
                self.server_specific_data[channel.server]['last_np_msg'] = None
                skipped = True
                player.skip()
                entries_added.pop()

        await self.safe_delete_message(busymsg)

        songs_added = len(entries_added)
        tnow = time.time()
        ttime = tnow - t0
        wait_per_song = 1.2
        # TODO: actually calculate wait per song in the process function and return that too

        # This is technically inaccurate since bad songs are ignored but still take up time
        log.info("Processed {}/{} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
            songs_processed,
            num_songs,
            fixg(ttime),
            ttime / num_songs if num_songs else 0,
            ttime / num_songs - wait_per_song if num_songs - wait_per_song else 0,
            fixg(wait_per_song * num_songs))
        )

        if not songs_added:
            basetext = "No songs were added, all songs were over max duration (%ss)" % permissions.max_song_length
            if skipped:
                basetext += "\nAdditionally, the current song was skipped for being too long."

            raise exceptions.CommandError(basetext, expire_in=30)

        return Response("Enqueued {} songs to be played in {} seconds".format(
            songs_added, fixg(ttime, 1)), delete_after=30)

    async def cmd_stream(self, player, channel, author, permissions, song_url):
        """
        Usage:
            {command_prefix}stream song_link

        Enqueue a media stream.
        This could mean an actual stream like Twitch or shoutcast, or simply streaming
        media without predownloading it.  Note: FFmpeg is notoriously bad at handling
        streams, especially on poor connections.  You have been warned.
        """

        song_url = song_url.strip('<>')

        if permissions.max_songs and player.playlist.count_for_user(author) >= permissions.max_songs:
            raise exceptions.PermissionsError(
                "You have reached your enqueued song limit (%s)" % permissions.max_songs, expire_in=30
            )

        await self.send_typing(channel)
        await player.playlist.add_stream_entry(song_url, channel=channel, author=author)

        return Response(":+1:", delete_after=6)

    async def cmd_search(self, player, channel, author, permissions, leftover_args):
        """
        Usage:
            {command_prefix}search [service] [number] query

        Searches a service for a video and adds it to the queue.
        - service: any one of the following services:
            - youtube (yt) (default if unspecified)
            - soundcloud (sc)
            - yahoo (yh)
        - number: return a number of video results and waits for user to choose one
          - defaults to 1 if unspecified
          - note: If your search query starts with a number,
                  you must put your query in quotes
            - ex: {command_prefix}search 2 "I ran seagulls"
        """

        if permissions.max_songs and player.playlist.count_for_user(author) > permissions.max_songs:
            raise exceptions.PermissionsError(
                "You have reached your playlist item limit (%s)" % permissions.max_songs,
                expire_in=30
            )

        def argcheck():
            if not leftover_args:
                # noinspection PyUnresolvedReferences
                raise exceptions.CommandError(
                    "Please specify a search query.\n%s" % dedent(
                        self.cmd_search.__doc__.format(command_prefix=self.config.command_prefix)),
                    expire_in=60
                )

        argcheck()

        try:
            leftover_args = shlex.split(' '.join(leftover_args))
        except ValueError:
            raise exceptions.CommandError("Please quote your search query properly.", expire_in=30)

        service = 'youtube'
        items_requested = 3
        max_items = 10  # this can be whatever, but since ytdl uses about 1000, a small number might be better
        services = {
            'youtube': 'ytsearch',
            'soundcloud': 'scsearch',
            'yahoo': 'yvsearch',
            'yt': 'ytsearch',
            'sc': 'scsearch',
            'yh': 'yvsearch'
        }

        if leftover_args[0] in services:
            service = leftover_args.pop(0)
            argcheck()

        if leftover_args[0].isdigit():
            items_requested = int(leftover_args.pop(0))
            argcheck()

            if items_requested > max_items:
                raise exceptions.CommandError("You cannot search for more than %s videos" % max_items)

        # Look jake, if you see this and go "what the fuck are you doing"
        # and have a better idea on how to do this, i'd be delighted to know.
        # I don't want to just do ' '.join(leftover_args).strip("\"'")
        # Because that eats both quotes if they're there
        # where I only want to eat the outermost ones
        if leftover_args[0][0] in '\'"':
            lchar = leftover_args[0][0]
            leftover_args[0] = leftover_args[0].lstrip(lchar)
            leftover_args[-1] = leftover_args[-1].rstrip(lchar)

        search_query = '%s%s:%s' % (services[service], items_requested, ' '.join(leftover_args))

        search_msg = await self.send_message(channel, "Searching for videos...")
        await self.send_typing(channel)

        try:
            info = await self.downloader.extract_info(player.playlist.loop, search_query, download=False, process=True)

        except Exception as e:
            await self.safe_edit_message(search_msg, str(e), send_if_fail=True)
            return
        else:
            await self.safe_delete_message(search_msg)

        if not info:
            return Response("No videos found.", delete_after=30)

        def check(m):
            return (
                m.content.lower()[0] in 'yn' or
                # hardcoded function name weeee
                m.content.lower().startswith('{}{}'.format(self.config.command_prefix, 'search')) or
                m.content.lower().startswith('exit'))

        for e in info['entries']:
            result_message = await self.safe_send_message(channel, "Result %s/%s: %s" % (
                info['entries'].index(e) + 1, len(info['entries']), e['webpage_url']))

            confirm_message = await self.safe_send_message(channel, "Is this ok? Type `y`, `n` or `exit`")
            response_message = await self.wait_for_message(30, author=author, channel=channel, check=check)

            if not response_message:
                await self.safe_delete_message(result_message)
                await self.safe_delete_message(confirm_message)
                return Response("Ok nevermind.", delete_after=30)

            # They started a new search query so lets clean up and bugger off
            elif response_message.content.startswith(self.config.command_prefix) or \
                    response_message.content.lower().startswith('exit'):

                await self.safe_delete_message(result_message)
                await self.safe_delete_message(confirm_message)
                return

            if response_message.content.lower().startswith('y'):
                await self.safe_delete_message(result_message)
                await self.safe_delete_message(confirm_message)
                await self.safe_delete_message(response_message)

                await self.cmd_play(player, channel, author, permissions, [], e['webpage_url'])

                return Response("Alright, coming right up!", delete_after=30)
            else:
                await self.safe_delete_message(result_message)
                await self.safe_delete_message(confirm_message)
                await self.safe_delete_message(response_message)

        return Response("Oh well \N{SLIGHTLY FROWNING FACE}", delete_after=30)

    async def cmd_np(self, player, channel, server, message):
        """
        Usage:
            {command_prefix}np

        Displays the current song in chat.
        """

        if player.current_entry:
            if self.server_specific_data[server]['last_np_msg']:
                await self.safe_delete_message(self.server_specific_data[server]['last_np_msg'])
                self.server_specific_data[server]['last_np_msg'] = None

            # TODO: Fix timedelta garbage with util function
            song_progress = ftimedelta(timedelta(seconds=player.progress))
            song_total = ftimedelta(timedelta(seconds=player.current_entry.duration))

            streaming = isinstance(player.current_entry, StreamPlaylistEntry)
            prog_str = ('`[{progress}]`' if streaming else '`[{progress}/{total}]`').format(
                progress=song_progress, total=song_total
            )
            prog_bar_str = ''

            # percentage shows how much of the current song has already been played
            percentage = 0.0
            if player.current_entry.duration > 0:
                percentage = player.progress / player.current_entry.duration
            """
            This for loop adds  empty or full squares to prog_bar_str (it could look like
            [■■■■■■■■■■□□□□□□□□□□□□□□□□□□□□□□□□□□□□□□]
            if for example the song has already played 25% of the songs duration
            """
            progress_bar_length = 30
            for i in range(progress_bar_length):
                if (percentage < 1 / progress_bar_length * i):
                    prog_bar_str += '□'
                else:
                    prog_bar_str += '■'

            action_text = 'Streaming' if streaming else 'Playing'

            np_text = ""

            if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
                np_text = "Now {action}: **{title}** added by **{author}**\nProgress: {progress_bar} {progress}\n\N{WHITE RIGHT POINTING BACKHAND INDEX} <{url}>".format(
                    action=action_text,
                    title=player.current_entry.title,
                    author=player.current_entry.meta['author'].name,
                    progress_bar=prog_bar_str,
                    progress=prog_str,
                    url=player.current_entry.url
                )
            else:
                np_text = "Now {action}: **{title}**\nProgress: {progress_bar} {progress}\n\N{WHITE RIGHT POINTING BACKHAND INDEX} <{url}>".format(
                    action=action_text,
                    title=player.current_entry.title,
                    progress_bar=prog_bar_str,
                    progress=prog_str,
                    url=player.current_entry.url
                )

            likers = ""
            if await self.autoplaylist.get_likers(player.current_entry.url):
                for each_user in await self.autoplaylist.get_likers(player.current_entry.url):
                    # strip off the unique identifiers
                    # I'm not using the meta data since technically it has no author so I wrote a get_likers function
                    if each_user.user_id == player.current_entry.meta['author'].id:
                        likers = likers + "**" + str(each_user) + "**" + ", "
                    else:
                        likers = likers + str(each_user) + ", "

                # slice off last " ,""
                likers = likers[:-2]

            #Getting all tags for song
            list_tags = list(filter(lambda tag: player.current_entry.url in self.metaData[tag], self.metaData.keys()))
            if len(list_tags) > 0:
                the_tags = "\nTags: "
                for each_tag in list_tags:
                    user = await self.autoplaylist.get_user(self._get_user(player.current_entry.meta['author'].id))
                    if getattr(user, 'mood', None) == each_tag:
                        the_tags += "**[" + each_tag + "]**, "
                    else:
                        the_tags += "[" + each_tag + "], "

                the_tags = the_tags[:-2]
            else:
                the_tags = ""

            song = await self.autoplaylist.find_song_by_url(player.current_entry.url)
            if song:
                np_text += "\nVolume: %s" % str(int(song.volume * 100))
                np_text += "\nPlay Count: %d" % song.play_count
                np_text += "\nLast Played: %s" % player.current_entry.meta.get('last_played', song.updt_dt_tm)
                if len(likers) > 0:
                    np_text += "\nLiked by: %s%s" % (likers, the_tags)

            #self.server_specific_data[server]['last_np_msg'] = await self.safe_send_message(channel, np_text)
            #await self._manual_delete_check(message)

            return Response(np_text, delete_after=30)
        else:
            return Response(
                'There are no songs queued! Queue something with {}play.'.format(self.config.command_prefix),
                delete_after=30
            )

    async def cmd_summon(self, channel, server, author, voice_channel):
        """
        Usage:
            {command_prefix}summon

        Call the bot to the summoner's voice channel.
        """

        if not author.voice_channel:
            raise exceptions.CommandError('You are not in a voice channel!')

        voice_client = self.voice_client_in(server)
        if voice_client and server == author.voice_channel.server:
            await voice_client.move_to(author.voice_channel)
            return

        # move to _verify_vc_perms?
        chperms = author.voice_channel.permissions_for(server.me)

        if not chperms.connect:
            log.warning("Cannot join channel \"{}\", no permission.".format(author.voice_channel.name))
            return Response(
                "```Cannot join channel \"{}\", no permission.```".format(author.voice_channel.name),
                delete_after=25
            )

        elif not chperms.speak:
            log.warning("Will not join channel \"{}\", no permission to speak.".format(author.voice_channel.name))
            return Response(
                "```Will not join channel \"{}\", no permission to speak.```".format(author.voice_channel.name),
                delete_after=25
            )

        log.info("Joining {0.server.name}/{0.name}".format(author.voice_channel))

        player = await self.get_player(author.voice_channel, create=True, deserialize=self.config.persistent_queue)

        if player.is_stopped:
            player.play()

        if self.config.auto_playlist:
            await self.on_player_finished_playing(player)

    async def cmd_pause(self, player):
        """
        Usage:
            {command_prefix}pause

        Pauses playback of the current song.
        """

        if player.is_playing:
            player.pause()

        else:
            raise exceptions.CommandError('Player is not playing.', expire_in=30)

    async def cmd_resume(self, player):
        """
        Usage:
            {command_prefix}resume

        Resumes playback of a paused song.
        """

        if player.is_paused:
            player.resume()

        else:
            raise exceptions.CommandError('Player is not paused.', expire_in=30)

    async def cmd_shuffle(self, channel, player):
        """
        Usage:
            {command_prefix}shuffle

        Shuffles the playlist.
        """

        player.playlist.shuffle()

        cards = ['\N{BLACK SPADE SUIT}', '\N{BLACK CLUB SUIT}', '\N{BLACK HEART SUIT}', '\N{BLACK DIAMOND SUIT}']
        random.shuffle(cards)

        hand = await self.send_message(channel, ' '.join(cards))
        await asyncio.sleep(0.6)

        for x in range(4):
            random.shuffle(cards)
            await self.safe_edit_message(hand, ' '.join(cards))
            await asyncio.sleep(0.6)

        await self.safe_delete_message(hand, quiet=True)
        return Response("\N{OK HAND SIGN}", delete_after=15)

    async def cmd_clear(self, player, author):
        """
        Usage:
            {command_prefix}clear

        Clears the playlist.
        """

        player.playlist.clear()
        return Response('\N{PUT LITTER IN ITS PLACE SYMBOL}', delete_after=20)

    async def cmd_skip(self, player, channel, author, message, permissions, voice_channel):
        """
        Usage:
            {command_prefix}skip

        Skips the current song when enough votes are cast, or by the bot owner.
        """

        if player.is_stopped:
            raise exceptions.CommandError("Can't skip! The player is not playing!", expire_in=20)

        if (self._get_channel(author.id, voice=True) != self._get_channel(self.user.id, voice=True)):
            raise exceptions.CommandError('You are not in the musicbot\'s voice channel!')

        if not player.current_entry:
            if player.playlist.peek():
                if player.playlist.peek()._is_downloading:
                    return Response("The next song (%s) is downloading, please wait." % player.playlist.peek().title)

                elif player.playlist.peek().is_downloaded:
                    print("The next song will be played shortly.  Please wait.")
                else:
                    print("Something odd is happening.  "
                          "You might want to restart the bot if it doesn't start working.")
            else:
                print("Something strange is happening.  "
                      "You might want to restart the bot if it doesn't start working.")

        likers = await self.autoplaylist.get_likers(player.current_entry.url)
        if not likers:
            likers = []

        if author.id == self.config.owner_id \
                or permissions.instaskip \
                or author == player.current_entry.meta.get('author', None) \
                or author in likers \
                or any(list(filter(lambda userID: userID in likers, self.get_ghost_exist(author.id)))) \
                or player.current_entry.disliked == True:

            player.skip()  # check autopause stuff here
            await self._manual_delete_check(message)
            return

        # TODO: ignore person if they're deaf or take them out of the list or something?
        # Currently is recounted if they vote, deafen, then vote

        num_voice = sum(1 for m in voice_channel.voice_members if not (
            m.deaf or m.self_deaf or m.id in [self.config.owner_id, self.user.id]))

        num_skips = player.skip_state.add_skipper(author.id, message)

        skips_remaining = min(
            self.config.skips_required,
            sane_round_int(num_voice * self.config.skip_ratio_required)
        ) - num_skips

        if skips_remaining <= 0:
            player.skip()  # check autopause stuff here
            return Response(
                'your skip for **{}** was acknowledged.'
                '\nThe vote to skip has been passed.{}'.format(
                    player.current_entry.title,
                    ' Next song coming up!' if player.playlist.peek() else ''
                ),
                reply=True,
                delete_after=20
            )

        else:
            # TODO: When a song gets skipped, delete the old x needed to skip messages
            return Response(
                'your skip for **{}** was acknowledged.'
                '\n**{}** more {} required to vote to skip this song.'.format(
                    player.current_entry.title,
                    skips_remaining,
                    'person is' if skips_remaining == 1 else 'people are'
                ),
                reply=True,
                delete_after=20
            )

    async def cmd_volume(self, message, player, new_volume=None):
        """
        Usage:
            {command_prefix}volume (+/-)[volume]

        Sets the playback volume. Accepted values are from 1 to 100.
        Putting + or - before the volume will make the volume change relative to the current volume.
        """

        if not new_volume:
            return Response('Current volume: `%s%%`' % int(player.volume * 100), reply=True, delete_after=20)

        relative = False
        if new_volume[0] in '+-':
            relative = True

        try:
            new_volume = int(new_volume)

        except ValueError:
            raise exceptions.CommandError('{} is not a valid number'.format(new_volume), expire_in=20)

        vol_change = None
        if relative:
            vol_change = new_volume
            new_volume += (player.volume * 100)

        old_volume = int(player.volume * 100)

        if 0 < new_volume <= 100:
            player.volume = new_volume / 100.0

            if player.current_entry:
                song = await self.autoplaylist.find_song_by_url(player.current_entry.url)
                if song:
                    song.volume = player.volume
                    if await self.autoplaylist.sqlfactory.song_update(song.url, song.title, song.play_count, song.volume, get_cur_dt_tm(), song.cret_dt_tm, song.url):
                        log.info("Updating stored volume to " + str(player.volume))
                    else:
                        log.warning("Failed updating stored volume to {} for song {}".format(str(player.volume), str(song)))

            return Response('Updated volume from %d to %d' % (old_volume, new_volume), reply=True, delete_after=20)

        else:
            if relative:
                raise exceptions.CommandError(
                    'Unreasonable volume change provided: {}{:+} -> {}%.  Provide a change between {} and {:+}.'.format(
                        old_volume, vol_change, old_volume + vol_change, 1 - old_volume, 100 - old_volume), expire_in=20)
            else:
                raise exceptions.CommandError(
                    'Unreasonable volume provided: {}%. Provide a value between 1 and 100.'.format(new_volume), expire_in=20)

    async def cmd_queue(self, channel, player):
        """
        Usage:
            {command_prefix}queue

        Prints the current song queue.
        """

        lines = []
        unlisted = 0
        andmoretext = '* ... and %s more*' % ('x' * len(player.playlist.entries))

        if player.current_entry:
            # TODO: Fix timedelta garbage with util function
            song_progress = ftimedelta(timedelta(seconds=player.progress))
            song_total = ftimedelta(timedelta(seconds=player.current_entry.duration))
            prog_str = '`[%s/%s]`' % (song_progress, song_total)

            if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
                lines.append("Currently Playing: **%s** added by **%s** %s\n" % (
                    player.current_entry.title, player.current_entry.meta['author'].name, prog_str))
            else:
                lines.append("Now Playing: **%s** %s\n" % (player.current_entry.title, prog_str))

        for i, item in enumerate(player.playlist, 1):
            if item.meta.get('channel', False) and item.meta.get('author', False):
                nextline = '`{}.` **{}** added by **{}**'.format(i, null_check_string(item, 'title'), item.meta['author'].name).strip()
            else:
                nextline = '`{}.` **{}**'.format(i, null_check_string(item, 'title')).strip()

            currentlinesum = sum(len(x) + 1 for x in lines)  # +1 is for newline char

            if currentlinesum + len(nextline) + len(andmoretext) > DISCORD_MSG_CHAR_LIMIT:
                if currentlinesum + len(andmoretext):
                    unlisted += 1
                    continue

            lines.append(nextline)

        if unlisted:
            lines.append('\n*... and %s more*' % unlisted)

        if not lines:
            lines.append(
                'There are no songs queued! Queue something with {}play.'.format(self.config.command_prefix))

        message = '\n'.join(lines)
        return Response(message, delete_after=30)

    async def cmd_clean(self, message, channel, server, author, search_range=50):
        """
        Usage:
            {command_prefix}clean [range]

        Removes up to [range] messages the bot has posted in chat. Default: 50, Max: 1000
        """

        try:
            float(search_range)  # lazy check
            search_range = min(int(search_range), 1000)
        except:
            return Response("enter a number.  NUMBER.  That means digits.  `15`.  Etc.", reply=True, delete_after=8)

        await self.safe_delete_message(message, quiet=True)

        def is_possible_command_invoke(entry):
            valid_call = any(
                entry.content.startswith(prefix) for prefix in [self.config.command_prefix])  # can be expanded
            return valid_call and not entry.content[1:2].isspace()

        delete_invokes = True
        delete_all = channel.permissions_for(author).manage_messages or self.config.owner_id == author.id

        def check(message):
            if is_possible_command_invoke(message) and delete_invokes:
                return delete_all or message.author == author
            return message.author == self.user

        if self.user.bot:
            if channel.permissions_for(server.me).manage_messages:
                deleted = await self.purge_from(channel, check=check, limit=search_range, before=message)
                return Response('Cleaned up {} message{}.'.format(len(deleted), 's' * bool(deleted)), delete_after=15)

        deleted = 0
        async for entry in self.logs_from(channel, search_range, before=message):
            if entry == self.server_specific_data[channel.server]['last_np_msg']:
                continue

            if entry.author == self.user:
                await self.safe_delete_message(entry)
                deleted += 1
                await asyncio.sleep(0.21)

            if is_possible_command_invoke(entry) and delete_invokes:
                if delete_all or entry.author == author:
                    try:
                        await self.delete_message(entry)
                        await asyncio.sleep(0.21)
                        deleted += 1

                    except discord.Forbidden:
                        delete_invokes = False
                    except discord.HTTPException:
                        pass

        return Response('Cleaned up {} message{}.'.format(deleted, 's' * bool(deleted)), delete_after=6)

    async def cmd_pldump(self, channel, song_url):
        """
        Usage:
            {command_prefix}pldump url

        Dumps the individual urls of a playlist
        """

        try:
            info = await self.downloader.extract_info(self.loop, song_url.strip('<>'), download=False, process=False)
        except Exception as e:
            raise exceptions.CommandError("Could not extract info from input url\n%s\n" % e, expire_in=25)

        if not info:
            raise exceptions.CommandError("Could not extract info from input url, no data.", expire_in=25)

        if not info.get('entries', None):
            # TODO: Retarded playlist checking
            # set(url, webpageurl).difference(set(url))

            if info.get('url', None) != info.get('webpage_url', info.get('url', None)):
                raise exceptions.CommandError("This does not seem to be a playlist.", expire_in=25)
            else:
                return await self.cmd_pldump(channel, info.get(''))

        linegens = defaultdict(lambda: None, **{
            "youtube":    lambda d: 'https://www.youtube.com/watch?v=%s' % d['id'],
            "soundcloud": lambda d: d['url'],
            "bandcamp":   lambda d: d['url']
        })

        exfunc = linegens[info['extractor'].split(':')[0]]

        if not exfunc:
            raise exceptions.CommandError("Could not extract info from input url, unsupported playlist type.", expire_in=25)

        with BytesIO() as fcontent:
            for item in info['entries']:
                fcontent.write(exfunc(item).encode('utf8') + b'\n')

            fcontent.seek(0)
            await self.send_file(channel, fcontent, filename='playlist.txt', content="Here's the url dump for <%s>" % song_url)

        return Response("\N{OPEN MAILBOX WITH RAISED FLAG}", delete_after=20)

    async def cmd_listids(self, server, author, leftover_args, cat='all'):
        """
        Usage:
            {command_prefix}listids [categories]

        Lists the ids for various things.  Categories are:
           all, users, roles, channels
        """

        cats = ['channels', 'roles', 'users']

        if cat not in cats and cat != 'all':
            return Response(
                "Valid categories: " + ' '.join(['`%s`' % c for c in cats]),
                reply=True,
                delete_after=25
            )

        if cat == 'all':
            requested_cats = cats
        else:
            requested_cats = [cat] + [c.strip(',') for c in leftover_args]

        data = ['Your ID: %s' % author.id]

        for cur_cat in requested_cats:
            rawudata = None

            if cur_cat == 'users':
                data.append("\nUser IDs:")
                rawudata = ['%s #%s: %s' % (m.name, m.discriminator, m.id) for m in server.members]

            elif cur_cat == 'roles':
                data.append("\nRole IDs:")
                rawudata = ['%s: %s' % (r.name, r.id) for r in server.roles]

            elif cur_cat == 'channels':
                data.append("\nText Channel IDs:")
                tchans = [c for c in server.channels if c.type == discord.ChannelType.text]
                rawudata = ['%s: %s' % (c.name, c.id) for c in tchans]

                rawudata.append("\nVoice Channel IDs:")
                vchans = [c for c in server.channels if c.type == discord.ChannelType.voice]
                rawudata.extend('%s: %s' % (c.name, c.id) for c in vchans)

            if rawudata:
                data.extend(rawudata)

        with BytesIO() as sdata:
            sdata.writelines(d.encode('utf8') + b'\n' for d in data)
            sdata.seek(0)

            # TODO: Fix naming (Discord20API-ids.txt)
            await self.send_file(author, sdata, filename='%s-ids-%s.txt' % (server.name.replace(' ', '_'), cat))

        return Response("\N{OPEN MAILBOX WITH RAISED FLAG}", delete_after=20)

    async def cmd_perms(self, author, channel, server, permissions):
        """
        Usage:
            {command_prefix}perms

        Sends the user a list of their permissions.
        """

        lines = ['Command permissions in %s\n' % server.name, '```', '```']

        for perm in permissions.__dict__:
            if perm in ['user_list'] or permissions.__dict__[perm] == set():
                continue

            lines.insert(len(lines) - 1, "%s: %s" % (perm, permissions.__dict__[perm]))

        await self.send_message(author, '\n'.join(lines))
        return Response("\N{OPEN MAILBOX WITH RAISED FLAG}", delete_after=20)

    async def cmd_patchnotes(self, leftover_args):
        """
        Usage:
            {command_prefix}patchnotes

        Displays the most recent commit message on the repository
        """
        file = load_file(self.config.last_commit_file)
        textblock = ""
        for each_line in file:
            textblock += each_line

        return Response("```\n" + textblock + "\n```", delete_after=30)

    async def cmd_playnow(self, player, channel, author, permissions, leftover_args, song_url):
        """
        Usage:
            {command_prefix}playnow song_link
            {command_prefix}playnow text to search for
        Stops the currently playing song and immediately plays the song requested. \
        If a link is not provided, the first result from a youtube search is played.
        """

        # immediate = True
        leftover_args.append("True")

        return await self.cmd_play(player, channel, author, permissions, leftover_args, song_url)

    @owner_only
    async def cmd_setname(self, leftover_args, name):
        """
        Usage:
            {command_prefix}setname name

        Changes the bot's username.
        Note: This operation is limited by discord to twice per hour.
        """

        name = ' '.join([name, *leftover_args])

        try:
            await self.edit_profile(username=name)

        except discord.HTTPException:
            raise exceptions.CommandError(
                "Failed to change name.  Did you change names too many times?  "
                "Remember name changes are limited to twice per hour.")

        except Exception as e:
            raise exceptions.CommandError(e, expire_in=20)

        return Response("\N{OK HAND SIGN}", delete_after=20)

    async def cmd_setnick(self, server, channel, leftover_args, nick):
        """
        Usage:
            {command_prefix}setnick nick

        Changes the bot's nickname.
        """

        if not channel.permissions_for(server.me).change_nickname:
            raise exceptions.CommandError("Unable to change nickname: no permission.")

        nick = ' '.join([nick, *leftover_args])

        try:
            await self.change_nickname(server.me, nick)
        except Exception as e:
            raise exceptions.CommandError(e, expire_in=20)

        return Response("\N{OK HAND SIGN}", delete_after=20)

    @owner_only
    async def cmd_setavatar(self, message, url=None):
        """
        Usage:
            {command_prefix}setavatar [url]

        Changes the bot's avatar.
        Attaching a file and leaving the url parameter blank also works.
        """

        if message.attachments:
            thing = message.attachments[0]['url']
        else:
            thing = url.strip('<>')

        try:
            with aiohttp.Timeout(10):
                async with self.aiosession.get(thing) as res:
                    await self.edit_profile(avatar=await res.read())

        except Exception as e:
            raise exceptions.CommandError("Unable to change avatar: {}".format(e), expire_in=20)

        return Response("\N{OK HAND SIGN}", delete_after=20)


    async def cmd_disconnect(self, server):
        await self.disconnect_voice_client(server)
        return Response("\N{DASH SYMBOL}", delete_after=20)

    async def cmd_restart(self, channel):
        await self.safe_send_message(channel, "\N{WAVING HAND SIGN}")
        await self.disconnect_all_voice_clients()
        raise exceptions.RestartSignal()

    async def cmd_shutdown(self, channel):
        await self.safe_send_message(channel, "\N{WAVING HAND SIGN}")
        await self.disconnect_all_voice_clients()
        raise exceptions.TerminateSignal()

    async def cmd_execute(self, server, channel, author, message):

        lines = message.content
        print("COMMAND ===" + lines)
        lines = lines.split("\n")

        for each_line in lines:
            if "```" not in each_line or "execute" not in each_line:
                await self.on_message(each_line)
        return

    @dev_only
    async def cmd_breakpoint(self, message):
        log.critical("Activating debug breakpoint")
        return

    @dev_only
    async def cmd_objgraph(self, channel, func='most_common_types()'):
        import objgraph

        await self.send_typing(channel)

        if func == 'growth':
            f = StringIO()
            objgraph.show_growth(limit=10, file=f)
            f.seek(0)
            data = f.read()
            f.close()

        elif func == 'leaks':
            f = StringIO()
            objgraph.show_most_common_types(objects=objgraph.get_leaking_objects(), file=f)
            f.seek(0)
            data = f.read()
            f.close()

        elif func == 'leakstats':
            data = objgraph.typestats(objects=objgraph.get_leaking_objects())

        else:
            data = eval('objgraph.' + func)

        return Response(data, codeblock='py')

    @dev_only
    async def cmd_debug(self, message, _player, *, data):
        codeblock = "```py\n{}\n```"
        result = None

        if data.startswith('```') and data.endswith('```'):
            data = '\n'.join(data.rstrip('`\n').split('\n')[1:])

        code = data.strip('` \n')

        try:
            result = eval(code)
        except:
            try:
                exec(code)
            except Exception as e:
                traceback.print_exc(chain=False)
                return Response("{}: {}".format(type(e).__name__, e))

        if asyncio.iscoroutine(result):
            result = await result

        return Response(codeblock.format(result))

    @dev_only
    async def cmd_dumplist(self, author, user_id):

        data = []

        user = await self.autoplaylist.get_user(user_id)
        if user != None:
            song_list = await self.autoplaylist.get_user_songs(user.user_id)
            for each_song in song_list:
                if each_song:
                    data.append(str(each_song) + ", Playcount: " + str(each_song.play_count) + "\r\n")

            if len(song_list) == 0:
                data.append("Your auto playlist is empty.")

            # sorts the mylist alphabetically Note: only works for ASCII characters
            data.sort(key=str.lower)

            with BytesIO() as sdata:
                sdata.writelines(d.encode('utf8') for d in data)
                sdata.seek(0)

                # TODO: Fix naming (Discord20API-ids.txt)
                await self.send_file(author, sdata, filename='%s-autoplaylist.txt' % self._get_user(user_id).name)
        else:
            return Response("There's no one with that id in this channel!")
            
    @dev_only
    async def cmd_run_tests(self):

        # Test details
        # User ID: Jadedtdt
        # Title: Armin van Buuren - This Is A Test (Extended Mix)
        # URL: https://www.youtube.com/watch?v=fIrrHUaXpAE

        user_id = '181268300301336576'
        title = 'Armin van Buuren - This Is A Test (Extended Mix)'
        url = 'https://www.youtube.com/watch?v=fIrrHUaXpAE'

        dict_tests = {
            "new_like": False,
            "only_dislike": False,
            "like_other_liker": False,
            "dislike_other_liker": False,
            "self_dislike": False,
            "strong_dislike": False
        }
        response_str = ''

        # User likes song never added before
        success_count, result_set = await self.autoplaylist.sqlfactory.execute('SELECT COUNT(*) FROM USER_SONG WHERE URL = %s', [url])
        count_pre = result_set[0]
        if count_pre[0] == '0':
            success_user_like = await self.autoplaylist.user_like_song(user_id, url, title)
            if success_user_like:
                success_count_us, result_set_us = await self.autoplaylist.sqlfactory.execute('SELECT COUNT(*) FROM USER_SONG WHERE URL = %s', [url])
                count_post_us = result_set_us[0]

                success_count_s, result_set_s = await self.autoplaylist.sqlfactory.execute('SELECT COUNT(*) FROM SONG WHERE URL = %s', [url])
                count_post_s = result_set_s[0]
                if success_count_us and success_count_s and count_post_us[0] == '1' and count_post_s[0] == '1':
                    dict_tests["new_like"] = True
                else:
                    response_str += "[new_like] Post Count was not 1. count_post_us[0][{count_us}], count_post_s[0][{count_s}]\n".format(count_us=count_post_us[0], count_s=count_post_s[0])
            else:
                response_str += "[new_like] user_like was not a success\n"
        else:
            response_str += "[new_like] Pre failed -> song already existed!\n"
            
        # User dislikes song where they're the only liker


        # User likes song liked by someone else

        # User dislike song liked by someone else

        # User likes song they already like

        # User dislikes song they didn't already like


        for each_test in dict_tests.keys():
            response_str += "Test={desc}...{sts}\n".format(desc=each_test, sts="PASS" if dict_tests[each_test] else "FAIL")
        return Response(response_str)

        

    async def on_message(self, message):
        await self.wait_until_ready()

        message_content = message.content.strip()
        if not message_content.startswith(self.config.command_prefix):
            return

        if message.author == self.user:
            log.warning("Ignoring command from myself ({})".format(message.content))
            return

        if self.config.bound_channels and message.channel.id not in self.config.bound_channels and not message.channel.is_private:
            return  # if I want to log this I just move it under the prefix check

        command, *args = message_content.split(' ') # Uh, doesn't this break prefixes with spaces in them (it doesn't, config parser already breaks them)
        command = command[len(self.config.command_prefix):].lower().strip()

        handler = getattr(self, 'cmd_' + command, None)
        if not handler:
            return

        if message.channel.is_private:
            if not (message.author.id == self.config.owner_id and command == 'joinserver'):
                await self.send_message(message.channel, 'You cannot use this bot in private messages.')
                return

        if message.author.id in self.blacklist and message.author.id != self.config.owner_id:
            log.warning("User blacklisted: {0.id}/{0!s} ({1})".format(message.author, command))
            return

        else:
            log.info("{0.id}/{0!s}: {1}".format(message.author, message_content.replace('\n', '\n... ')))

        # check if user needs created
        user = await self.autoplaylist.get_user(message.author.id)
        if not user:
            discord_member = self._get_user(message.author.id)
            new_user = User(discord_member.id, discord_member.name)
            log.error("[ON_MESSAGE] Creating User profile for " + null_check_string(new_user, 'user_name'))
            self.email_util.send_exception(str(new_user), None, "[ON_MESSAGE] Creating User profile for " + null_check_string(new_user, 'user_name'))
            if not await self.autoplaylist.sqlfactory.user_create(new_user.user_id, new_user.user_name, new_user.mood, new_user.yti_url, get_cur_dt_tm(), get_cur_dt_tm()):
                log.error("[ON_MESSAGE] Failed to create user profile for User {}".format(str(new_user)))

        user = await self.autoplaylist.get_user(message.author.id)
        member = self._get_user(message.author.id)
        if member.name != user.user_name:
            log.error("[ON_MESSAGE] Updating user name for User object. {} -> {}".format(user.user_name, member.name))
            old_name = user.user_name # just for auditing purposes
            user.user_name = member.name
            if await self.autoplaylist.sqlfactory.user_update(user.user_id, user.user_name, user.mood, user.yti_url, get_cur_dt_tm(), user.cret_dt_tm, user.user_id):
                self.email_util.send_exception(str(user), None, "[ON_MESSAGE] Updating user name for User object. {} -> {}".format(old_name, member.name))
            else:
                self.email_util.send_exception(str(user), None, "[ON_MESSAGE] Failed Updating user name for User object. {} -> {}".format(old_name, member.name))

        user_permissions = self.permissions.for_user(message.author)

        argspec = inspect.signature(handler)
        params = argspec.parameters.copy()

        sentmsg = response = None

        # noinspection PyBroadException
        try:
            if user_permissions.ignore_non_voice and command in user_permissions.ignore_non_voice:
                await self._check_ignore_non_voice(message)

            handler_kwargs = {}
            if params.pop('message', None):
                handler_kwargs['message'] = message

            if params.pop('channel', None):
                handler_kwargs['channel'] = message.channel

            if params.pop('author', None):
                handler_kwargs['author'] = message.author

            if params.pop('server', None):
                handler_kwargs['server'] = message.server

            if params.pop('player', None):
                handler_kwargs['player'] = await self.get_player(message.channel)

            if params.pop('_player', None):
                handler_kwargs['_player'] = self.get_player_in(message.server)

            if params.pop('permissions', None):
                handler_kwargs['permissions'] = user_permissions

            if params.pop('user_mentions', None):
                handler_kwargs['user_mentions'] = list(map(message.server.get_member, message.raw_mentions))

            if params.pop('channel_mentions', None):
                handler_kwargs['channel_mentions'] = list(map(message.server.get_channel, message.raw_channel_mentions))

            if params.pop('voice_channel', None):
                handler_kwargs['voice_channel'] = message.server.me.voice_channel

            if params.pop('leftover_args', None):
                handler_kwargs['leftover_args'] = args

            args_expected = []
            for key, param in list(params.items()):

                # parse (*args) as a list of args
                if param.kind == param.VAR_POSITIONAL:
                    handler_kwargs[key] = args
                    params.pop(key)
                    continue

                # parse (*, args) as args rejoined as a string
                # multiple of these arguments will have the same value
                if param.kind == param.KEYWORD_ONLY and param.default == param.empty:
                    handler_kwargs[key] = ' '.join(args)
                    params.pop(key)
                    continue

                doc_key = '[{}={}]'.format(key, param.default) if param.default is not param.empty else key
                args_expected.append(doc_key)

                # Ignore keyword args with default values when the command had no arguments
                if not args and param.default is not param.empty:
                    params.pop(key)
                    continue

                # Assign given values to positional arguments
                if args:
                    arg_value = args.pop(0)
                    handler_kwargs[key] = arg_value
                    params.pop(key)

            if message.author.id != self.config.owner_id:
                if user_permissions.command_whitelist and command not in user_permissions.command_whitelist:
                    raise exceptions.PermissionsError(
                        "This command is not enabled for your group ({}).".format(user_permissions.name),
                        expire_in=20)

                elif user_permissions.command_blacklist and command in user_permissions.command_blacklist:
                    raise exceptions.PermissionsError(
                        "This command is disabled for your group ({}).".format(user_permissions.name),
                        expire_in=20)

            # Invalid usage, return docstring
            if params:
                docs = getattr(handler, '__doc__', None)
                if not docs:
                    docs = 'Usage: {}{} {}'.format(
                        self.config.command_prefix,
                        command,
                        ' '.join(args_expected)
                    )

                docs = dedent(docs)
                await self.safe_send_message(
                    message.channel,
                    '```\n{}\n```'.format(docs.format(command_prefix=self.config.command_prefix)),
                    expire_in=60
                )
                return

            response = await handler(**handler_kwargs)
            if response and isinstance(response, Response):
                content = response.content
                if response.reply:
                    content = '{}, {}'.format(message.author.mention, content)

                sentmsg = await self.safe_send_message(
                    message.channel, content,
                    expire_in=response.delete_after if self.config.delete_messages else 0,
                    also_delete=message if self.config.delete_invoking else None
                )

            log.info("[" + str(datetime.now()) + "][" + command.upper() + "] " + str(message.author))

            #FIXME replace with some persistence query?
            #self.autoplaylist.store(self._url_to_song_, self.users_list)

        except (exceptions.CommandError, exceptions.HelpfulError, exceptions.ExtractionError) as e:
            log.error("Error in {0}: {1.__class__.__name__}: {1.message}".format(command, e), exc_info=True)

            expirein = e.expire_in if self.config.delete_messages else None
            alsodelete = message if self.config.delete_invoking else None

            await self.safe_send_message(
                message.channel,
                '```\n{}\n```'.format(e.message),
                expire_in=expirein,
                also_delete=alsodelete
            )

        except exceptions.Signal:
            raise

        except Exception:
            log.error("Exception in on_message", exc_info=True)
            if self.config.debug_mode:
                await self.safe_send_message(message.channel, '```\n{}\n```'.format(traceback.format_exc()))

        finally:
            if not sentmsg and not response and self.config.delete_invoking:
                await asyncio.sleep(5)
                await self.safe_delete_message(message, quiet=True)

    async def on_voice_state_update(self, before, after):
        if not self.init_ok:
            return # Ignore stuff before ready

        state = VoiceStateUpdate(before, after)

        if state.broken:
            log.voicedebug("Broken voice state update")
            return

        if state.resuming:
            log.debug("Resumed voice connection to {0.server.name}/{0.name}".format(state.voice_channel))

        if not state.changes:
            log.voicedebug("Empty voice state update, likely a session id change")
            return # Session id change, pointless event

        ################################

        log.voicedebug("Voice state update for {mem.id}/{mem!s} on {ser.name}/{vch.name} -> {dif}".format(
            mem = state.member,
            ser = state.server,
            vch = state.voice_channel,
            dif = state.changes
        ))

        if not state.is_about_my_voice_channel:
            return # Irrelevant channel

        if state.joining or state.leaving:
            log.info("{0.id}/{0!s} has {1} {2}/{3}".format(
                state.member,
                'joined' if state.joining else 'left',
                state.server,
                state.my_voice_channel
            ))

        if not self.config.auto_pause:
            return

        autopause_msg = "{state} in {channel.server.name}/{channel.name} {reason}"

        auto_paused = self.server_specific_data[after.server]['auto_paused']
        player = await self.get_player(state.my_voice_channel)

        if not state.empty(old_channel=state.leaving):
            if auto_paused and player.is_paused:
                log.info(autopause_msg.format(
                    state = "Unpausing",
                    channel = state.my_voice_channel,
                    reason = ""
                ).strip())

                self.server_specific_data[after.server]['auto_paused'] = False
                player.resume()
                
        elif state.joining and state.empty() and player.is_playing:
            log.info(autopause_msg.format(
                state = "Pausing",
                channel = state.my_voice_channel,
                reason = "(joining empty channel)"
            ).strip())

            self.server_specific_data[after.server]['auto_paused'] = True
            player.pause()
            return

        if not state.is_about_me:
            if state.empty(old_channel=state.leaving):
                if not auto_paused and player.is_playing:
                    log.info(autopause_msg.format(
                        state = "Pausing",
                        channel = state.my_voice_channel,
                        reason = "(empty channel)"
                    ).strip())

                    self.server_specific_data[after.server]['auto_paused'] = True
                    player.pause()

    async def on_server_update(self, before:discord.Server, after:discord.Server):
        if before.region != after.region:
            log.warning("Server \"%s\" changed regions: %s -> %s" % (after.name, before.region, after.region))

            await self.reconnect_voice_client(after)

    async def on_server_join(self, server:discord.Server):
        log.info("Bot has been joined server: {}".format(server.name))

        if not self.user.bot:
            alertmsg = "<@{uid}> Hi I'm a musicbot please mute me."

            if server.id == "81384788765712384" and not server.unavailable: # Discord API
                playground = server.get_channel("94831883505905664") or discord.utils.get(server.channels, name='playground') or server
                await self.safe_send_message(playground, alertmsg.format(uid="98295630480314368")) # fake abal

            elif server.id == "129489631539494912" and not server.unavailable: # Rhino Bot Help
                bot_testing = server.get_channel("134771894292316160") or discord.utils.get(server.channels, name='bot-testing') or server
                await self.safe_send_message(bot_testing, alertmsg.format(uid="98295630480314368")) # also fake abal

        log.debug("Creating data folder for server %s", server.id)
        pathlib.Path('data/%s/' % server.id).mkdir(exist_ok=True)

    async def on_server_remove(self, server: discord.Server):
        log.info("Bot has been removed from server: {}".format(server.name))
        log.debug('Updated server list:')
        [log.debug(' - ' + s.name) for s in self.servers]

        if server.id in self.players:
            self.players.pop(server.id).kill()


    async def on_server_available(self, server: discord.Server):
        if not self.init_ok:
            return # Ignore pre-ready events

        log.debug("Server \"{}\" has become available.".format(server.name))

        player = self.get_player_in(server)

        if player and player.is_paused:
            av_paused = self.server_specific_data[server]['availability_paused']

            if av_paused:
                log.debug("Resuming player in \"{}\" due to availability.".format(server.name))
                self.server_specific_data[server]['availability_paused'] = False
                player.resume()

    async def on_server_unavailable(self, server: discord.Server):
        log.debug("Server \"{}\" has become unavailable.".format(server.name))

        player = self.get_player_in(server)

        if player and player.is_playing:
            log.debug("Pausing player in \"{}\" due to unavailability.".format(server.name))
            self.server_specific_data[server]['availability_paused'] = True
            player.pause()
