import os
import sys
import time
import shlex
import shutil
import inspect
import aiohttp
import discord
import asyncio
import traceback
import random

import pafy

from discord import utils
from discord.object import Object
from discord.enums import ChannelType
from discord.voice_client import VoiceClient
from discord.ext.commands.bot import _get_variable

from io import BytesIO
from functools import wraps
from textwrap import dedent
from datetime import timedelta, datetime
from collections import defaultdict

from musicbot.config import Config, ConfigDefaults
from musicbot.musicClass import Music
from musicbot.permissions import Permissions, PermissionsDefaults
from musicbot.player import MusicPlayer
from musicbot.playlist import Playlist
from musicbot.user import User
from musicbot.utils import *

from . import exceptions
from . import downloader
from .opus_loader import load_opus_lib
from .constants import VERSION as BOTVERSION
from .constants import DISCORD_MSG_CHAR_LIMIT, AUDIO_CACHE_PATH, TITLE_URL_SEPARATOR, URL_LIKERS_SEPARATOR, LIKERS_DELIMETER

load_opus_lib()

class SkipState:
    def __init__(self):
        self.skippers = set()
        self.skip_msgs = set()

    @property
    def skip_count(self):
        return len(self.skippers)

    def reset(self):
        self.skippers.clear()
        self.skip_msgs.clear()

    def add_skipper(self, skipper, msg):
        self.skippers.add(skipper)
        self.skip_msgs.add(msg)
        return self.skip_count

class Response:
    def __init__(self, content, reply=False, delete_after=0):
        self.content = content
        self.reply = reply
        self.delete_after = delete_after

class MusicBot(discord.Client):

    def __init__(self, config_file=ConfigDefaults.options_file, perms_file=PermissionsDefaults.perms_file):
        random.seed()
        self.players = {}
        self.the_voice_clients = {}
        self.metaData = {}
        self.ghost_list = {}
        self.list_Played = []
        self.len_list_Played = 20
        self.locks = defaultdict(asyncio.Lock)
        self.voice_client_connect_lock = asyncio.Lock()
        self.voice_client_move_lock = asyncio.Lock()

        self.config = Config(config_file)
        self.permissions = Permissions(perms_file, grant_all=[self.config.owner_id])

        self.blacklist = set(load_file(self.config.blacklist_file))
        #self.autoplaylist = load_file(self.config.auto_playlist_file)
        self.last_modified_ts_apl = -1
        self.last_modified_ts_users = -1
        self.autoplaylist = load_pickle(self.config.auto_playlist_pickle)
        self.users_list = load_pickle(self.config.users_list_pickle)
        #self.users_list = []
        self.wholeMetadata = load_file(self.config.metadata_file)
        self.downloader = downloader.Downloader(download_folder=AUDIO_CACHE_PATH)

        self.exit_signal = None
        self.init_ok = False
        self.cached_client_id = None

        ########################
        # housekeeping functions
        ########################
        # tweak delimeters - parses any legacy autoplaylists and reformats it to the current format
        # remove_duplicates - when combining multiple versions of autoplaylists, sometimes you have duplicate
        #                     entries with different users liking the song. this joins the two lists
        # update_song_names - grabs the title of the youtube song and stores in the autoplaylist file
        #
        ########################
        #self.tweak_delimiters()
        #self.remove_duplicates()
        #theoretically we shouldn't need this anymore
        #self.update_song_names()

        #self.users_list = []

        if not self.autoplaylist:
            print("Warning: Autoplaylist is empty, disabling.")
            self.config.auto_playlist = False
        else:
            '''
            # using autoplaylist

            # initializes APLs for each user
            # if the TITLE_URL delimeter is found, that means it's already added the title so we don't want to santize non-alphanumeric characters
            # if the URL_LIKERS delimeter is found, that means the song is liked by at least one person and we can split the string into URL and likers

            for each_song in self.autoplaylist:
                
                tuple_song_authors = each_song
                if TITLE_URL_SEPARATOR not in tuple_song_authors:
                    tuple_song_authors = sanitize_string(tuple_song_authors)

                # make sure we're not splitting with a delimeter that doesn't exist
                if URL_LIKERS_SEPARATOR in tuple_song_authors:
                    tuple_song_authors = tuple_song_authors.split(URL_LIKERS_SEPARATOR)
                else:
                    #print("No delimiter to split with. Assigning to MusicBot")
                    #self.assign_to_music_bot()
                    #break
                    continue
                #print(tuple_song_authors)

                try:
                    song_url, authors = tuple_song_authors
                except ValueError:
                    print("Error: " + str(tuple_song_authors))

                title = self.fetch_title(song_url)
                url = self.fetch_url(song_url)

                # for multiple likers, just iterate over comma separated authors
                authors = authors.split(LIKERS_DELIMETER)

                song = Music(title, url, authors)
                self.autoplaylist_temp.append(song)

                #print("A. " + str(song.getTitle()))
                #print("B. " + str(song.getURL()))
                #print("C. " + str(song.getLikers()))


                # fills our dictionary of user ids=>songs
                for each_author in each_song.getLikers():
                    print(each_song)
                    self._add_to_autoplaylist(each_song.title, each_song.url, each_author)

            #self.autoplaylist_temp = load_pickle(self.config.auto_playlist_pickle)
            #self.users_list = load_pickle(self.config.users_list_pickle)

        #print("1. " + str(self.users_list))
        #print("2. " + str(self.users_list))
        if (is_latest_pickle == True):
            self.last_modified_ts = store_pickle(self.config.users_list_pickle, self.users_list)
        '''
        

        #Setting up the metaData tags
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

        # initializes each user's mood to none
        #self.dict_moods = {}
        #for user in self.users_list.keys():
        #    self.dict_moods[user] = []

        # TODO: Do these properly
        ssd_defaults = {'last_np_msg': None, 'auto_paused': False}
        self.server_specific_data = defaultdict(lambda: dict(ssd_defaults))

        super().__init__()
        self.aiosession = aiohttp.ClientSession(loop=self.loop)
        self.http.user_agent += ' MusicBot/%s' % BOTVERSION

    ########################
    # assign_to_music_bot
    #
    # If no one likes a song, we assign it to the music bot in hopes that someone likes it while it's playing
    # Currently not possible to make the music bot dislike it without admin access (manual record modification)
    # Not recommended for use unless you're importing a legacy autoplaylist
    #
    # Precondition: song without any likers. i.e. "https://www.youtube.com"
    # Postcondition: the music bot likes the song. i.e. "https://www.youtube.com, 1234567890"
    ########################
    def assign_to_music_bot(self):
        i = 0
        for each_line in self.autoplaylist:
            # make sure we're not splitting with a delimeter that doesn't exist
            if ", " not in each_line:
                string = self.autoplaylist[i], str(self.user.id)
                self.autoplaylist[i] = sanitize_string(string)

            i += 1

        #write_file(self.config.auto_playlist_file, self.autoplaylist)
        if (is_latest_pickle(self.config.auto_playlist_pickle, self.last_modified_ts_apl) == False):
            self.last_modified_ts_apl = store_pickle(self.config.auto_playlist_pickle, self.autoplaylist)

    ########################
    # remove_duplicates
    #
    # When we have duplicate entries from merging autoplaylists, we could have multiple versions of songs with varying names, of varying names
    # This function strips down each entry to its url and makes sure there aren't any duplicates and if so, it combines the sets of the likers
    #
    # Precondition: messy autoplaylist file, most likely a conglomeration of several archived txt files
    # Postcondition: clean autoplaylist file, single instance of each video's url and the corresponding likers
    ########################
    def remove_duplicates(self):
        list_found = []
        list_urls = []

        for each_line in self.autoplaylist:
            if each_line not in list_found:

                url = self.fetch_url(each_line)

                # if this is a new url, add it to our list_found, otherwise ignore
                if url not in list_urls:
                    list_urls.append(url)
                    list_found.append(each_line)
                else:
                    # join/union the likers list
                    index = list_urls.index(url)
                    assert index != -1
                    cached_likers_line = list_found[index]

                    cached_title = self.fetch_title(cached_likers_line)
                    if cached_title is None:
                        cached_title = self.fetch_title(each_line)
                    new_likers_str = joinStr(self.fetch_likers(cached_likers_line), self.fetch_likers(each_line))
                    new_likers_line = cached_title + TITLE_URL_SEPARATOR + url + URL_LIKERS_SEPARATOR + new_likers_str
                    list_found[index] = new_likers_line

        self.autoplaylist = list_found
        #write_file(self.config.auto_playlist_file, self.autoplaylist)
        if (is_latest_pickle(self.config.auto_playlist_pickle, self.last_modified_ts_apl) == False):
            self.last_modified_ts_apl = store_pickle(self.config.auto_playlist_pickle, self.autoplaylist)

    ########################
    # update_song_names
    #
    # Takes the URL of the song and gets
    #
    # Precondition: line containing URL and likers
    # Postcondition: line containing name of song URL and likers separated by URL_LIKERS_SEPARATOR
    # Example: Panic! At The Disco: Death Of A Bachelor [OFFICIAL VIDEO] --- https://www.youtube.com/watch?v=R03cqGg40GU ~~~ 12345
    ########################
    def update_song_names(self):

        # TODO: update list name to something more accurate
        list_found = []

        for each_line in self.autoplaylist:
            # if a TITLE_URL_SEPARATOR is not found, that means the title needs to be loaded with pafy
            if TITLE_URL_SEPARATOR not in each_line:
                # let's assert the line is clean before we change its format
                each_line = sanitize_string(each_line)

                if URL_LIKERS_SEPARATOR in each_line:
                    (url, likers) = each_line.split(URL_LIKERS_SEPARATOR)
                else:
                    url = each_line
                    print("NO LIKERS FOR ", each_line)

                # in this case, each_line is strictly the URL
                if "youtube" in url or "youtu.be" in url:
                    song_title = ""
                    try:
                        song_title = str(pafy.new(url).title)
                    except:
                        # song has probably been removed to copywright
                        # if we don't add it to the list, it's the same as removing it
                        # notify_likers()?
                        continue

                    print("Processing: ", song_title)

                    # prepend url with its name and override
                    each_line = song_title + TITLE_URL_SEPARATOR + each_line

            list_found.append(each_line)

        self.autoplaylist = list_found
        #write_file(self.config.auto_playlist_file, self.autoplaylist)
        if (is_latest_pickle(self.config.auto_playlist_pickle, self.last_modified_ts_apl) == False):
            self.last_modified_ts_apl = store_pickle(self.config.auto_playlist_pickle, self.autoplaylist)

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

    # http://stackoverflow.com/questions/2556108/rreplace-how-to-replace-the-last-occurence-of-an-expression-in-a-string
    def rreplace(self, s, old, new, occurence):
        li = s.rsplit(old, occurence)
        return new.join(li)

    ########################
    # tweak_delimiters
    #
    # Updates the delimeters from commas to triple tildas incase titles have commas in them.
    #
    # Precondition: URLS and likers separated by ,
    # Postcondition: URLS and likers separated by the URL_LIKERS_SEPARATOR in constants.py
    ########################
    def tweak_delimiters(self):
        list_found = []
        for each_line in self.autoplaylist:
            each_line = sanitize_string(each_line)
            if URL_LIKERS_SEPARATOR not in each_line:
                each_line = self.rreplace(each_line, ", ", URL_LIKERS_SEPARATOR, 1)
            list_found.append(each_line)

        self.autoplaylist = list_found
        #write_file(self.config.auto_playlist_file, self.autoplaylist)
        if (is_latest_pickle(self.config.auto_playlist_pickle, self.last_modified_ts_apl) == False):
            self.last_modified_ts_apl = store_pickle(self.config.auto_playlist_pickle, self.autoplaylist)

    def get_user(self, discord_user):

        discord_id = -1

        # forces us to have id
        if not discord_user.isnumeric():
            discord_id = discord_user.id
        else:
            discord_id = discord_user

        for each_user in self.users_list:
            if each_user.getID() == discord_id:
                return each_user

        #print("No user found with info: ", discord_user)
        return None

    async def check_songs(self, song_url, author):
        orig = self.autoplaylist.copy()

        matched_song = None
        cached_song = None
        while self.find_song(song_url) != None and matched_song == None:
            cached_song = self.find_song(song_url)
            if author.id in cached_song.getLikers():
                matched_song = cached_song
            self.autoplaylist.remove(cached_song)

        if matched_song != None:
            song_url = matched_song.getURL()
        else:
            # none of them are our songs, so we'll try someone else's
            if cached_song != None:
                song_url = cached_song.getURL()

        self.autoplaylist = orig

        return song_url

    async def notify_likers(self, song, emsg=""):
        if song == None:
            print("Null song, no one to notify")
            return

        channel = self.get_channel(list(self.config.bound_channels)[0])

        likers = song.getLikers()
        likers_str = ""
        for each_liker in likers:
            likers_str += self._get_user(each_liker).mention + " "
        msg = 'Hey! %s. It seems like your video has been made unavailable.\n%s, %s\nReason: %s' % (likers_str, song.getTitle(), song.getURL(), emsg)
        await self.safe_send_message(channel, msg)

    # TODO: Add some sort of `denied` argument for a message to send when someone else tries to use it
    def owner_only(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Only allow the owner to use these commands
            orig_msg = _get_variable('message')

            if not orig_msg or orig_msg.author.id == self.config.owner_id:
                return await func(self, *args, **kwargs)
            else:
                raise exceptions.PermissionsError("only the owner can use this command", expire_in=30)

        return wrapper

    @staticmethod
    def _fixg(x, dp=2):
        return ('{:.%sf}' % dp).format(x).rstrip('0').rstrip('.')

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

    def _get_owner(self, voice=False):
        return self._get_user(self.config.owner_id, voice)

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

    # TODO: autosummon option to a specific channel
    async def _auto_summon(self):
        owner = self._get_owner(voice=True)
        if owner:
            self.safe_print("Found owner in \"%s\", attempting to join..." % owner.voice_channel.name)
            # TODO: Effort
            await self.cmd_summon(owner.voice_channel, owner, None)
            return owner.voice_channel

    async def _autojoin_channels(self, channels):
        joined_servers = []

        for channel in channels:
            if channel.server in joined_servers:
                print("Already joined a channel in %s, skipping" % channel.server.name)
                continue

            if channel and channel.type == discord.ChannelType.voice:
                self.safe_print("Attempting to autojoin %s in %s" % (channel.name, channel.server.name))

                chperms = channel.permissions_for(channel.server.me)

                if not chperms.connect:
                    self.safe_print("Cannot join channel \"%s\", no permission." % channel.name)
                    continue

                elif not chperms.speak:
                    self.safe_print("Will not join channel \"%s\", no permission to speak." % channel.name)
                    continue

                try:
                    player = await self.get_player(channel, create=True)

                    if player.is_stopped:
                        player.play()

                    if self.config.auto_playlist:
                        await self.on_player_finished_playing(player)

                    joined_servers.append(channel.server)
                except Exception as e:
                    if self.config.debug_mode:
                        traceback.print_exc()
                    print("Failed to join", channel.name)

            elif channel:
                print("Not joining %s on %s, that's a text channel." % (channel.name, channel.server.name))

            else:
                print("Invalid channel thing: " + channel)

    async def _wait_delete_msg(self, message, after):
        await asyncio.sleep(after)
        await self.safe_delete_message(message)

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

    async def generate_invite_link(self, *, permissions=None, server=None):
        if not self.cached_client_id:
            appinfo = await self.application_info()
            self.cached_client_id = appinfo.id

        return discord.utils.oauth_url(self.cached_client_id, permissions=permissions, server=server)

    async def get_voice_client(self, channel):
        if isinstance(channel, Object):
            channel = self.get_channel(channel.id)

        if getattr(channel, 'type', ChannelType.text) != ChannelType.voice:
            raise AttributeError('Channel passed must be a voice channel')

        with await self.voice_client_connect_lock:
            server = channel.server
            if server.id in self.the_voice_clients:
                return self.the_voice_clients[server.id]

            s_id = self.ws.wait_for('VOICE_STATE_UPDATE', lambda d: d.get('user_id') == self.user.id)
            _voice_data = self.ws.wait_for('VOICE_SERVER_UPDATE', lambda d: True)

            await self.ws.voice_state(server.id, channel.id)

            s_id_data = await asyncio.wait_for(s_id, timeout=10, loop=self.loop)
            voice_data = await asyncio.wait_for(_voice_data, timeout=10, loop=self.loop)
            session_id = s_id_data.get('session_id')

            kwargs = {
                'user': self.user,
                'channel': channel,
                'data': voice_data,
                'loop': self.loop,
                'session_id': session_id,
                'main_ws': self.ws
            }
            voice_client = VoiceClient(**kwargs)
            self.the_voice_clients[server.id] = voice_client

            retries = 3
            for x in range(retries):
                try:
                    print("Attempting connection...")
                    await asyncio.wait_for(voice_client.connect(), timeout=10, loop=self.loop)
                    print("Connection established.")
                    break
                except:
                    traceback.print_exc()
                    print("Failed to connect, retrying (%s/%s)..." % (x+1, retries))
                    await asyncio.sleep(1)
                    await self.ws.voice_state(server.id, None, self_mute=True)
                    await asyncio.sleep(1)

                    if x == retries-1:
                        raise exceptions.HelpfulError(
                            "Cannot establish connection to voice chat.  "
                            "Something may be blocking outgoing UDP connections.",

                            "This may be an issue with a firewall blocking UDP.  "
                            "Figure out what is blocking UDP and disable it.  "
                            "It's most likely a system firewall or overbearing anti-virus firewall.  "
                        )

            return voice_client

    async def mute_voice_client(self, channel, mute):
        await self._update_voice_state(channel, mute=mute)

    async def deafen_voice_client(self, channel, deaf):
        await self._update_voice_state(channel, deaf=deaf)

    async def move_voice_client(self, channel):
        await self._update_voice_state(channel)

    async def reconnect_voice_client(self, server):
        if server.id not in self.the_voice_clients:
            return

        vc = self.the_voice_clients.pop(server.id)
        _paused = False

        player = None
        if server.id in self.players:
            player = self.players[server.id]
            if player.is_playing:
                player.pause()
                _paused = True

        try:
            await vc.disconnect()
        except:
            print("Error disconnecting during reconnect")
            traceback.print_exc()

        await asyncio.sleep(0.1)

        if player:
            new_vc = await self.get_voice_client(vc.channel)
            player.reload_voice(new_vc)

            if player.is_paused and _paused:
                player.resume()

    async def disconnect_voice_client(self, server):
        if server.id not in self.the_voice_clients:
            return

        if server.id in self.players:
            self.players.pop(server.id).kill()

        await self.the_voice_clients.pop(server.id).disconnect()

    async def disconnect_all_voice_clients(self):
        for vc in self.the_voice_clients.copy().values():
            await self.disconnect_voice_client(vc.channel.server)

    async def _update_voice_state(self, channel, *, mute=False, deaf=False):
        if isinstance(channel, Object):
            channel = self.get_channel(channel.id)

        if getattr(channel, 'type', ChannelType.text) != ChannelType.voice:
            raise AttributeError('Channel passed must be a voice channel')

        # I'm not sure if this lock is actually needed
        with await self.voice_client_move_lock:
            server = channel.server

            payload = {
                'op': 4,
                'd': {
                    'guild_id': server.id,
                    'channel_id': channel.id,
                    'self_mute': mute,
                    'self_deaf': deaf
                }
            }

            await self.ws.send(utils.to_json(payload))
            self.the_voice_clients[server.id].channel = channel

    async def get_player(self, channel, create=False) -> MusicPlayer:
        server = channel.server

        if server.id not in self.players:
            if not create:
                raise exceptions.CommandError(
                    'The bot is not in a voice channel.  '
                    'Use %ssummon to summon it to your voice channel.' % self.config.command_prefix)

            voice_client = await self.get_voice_client(channel)

            playlist = Playlist(self)
            player = MusicPlayer(self, voice_client, playlist) \
                .on('play', self.on_player_play) \
                .on('resume', self.on_player_resume) \
                .on('pause', self.on_player_pause) \
                .on('stop', self.on_player_stop) \
                .on('finished-playing', self.on_player_finished_playing) \
                .on('entry-added', self.on_player_entry_added)

            player.skip_state = SkipState()
            self.players[server.id] = player

        return self.players[server.id]

    async def on_player_play(self, player, entry):
        await self.update_now_playing(entry)
        player.skip_state.reset()

        channel = entry.meta.get('channel', None)
        author = entry.meta.get('author', None)

        if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
            user = self.get_user(player.current_entry.meta['author'].id)

        else:
            # AutoPlayList playing

            likers = ""
            for each_user in self.get_likers(player.current_entry.url):
                # strip off the unique identifiers
                # I'm not using the meta data since technically it has no author so I wrote a get_likers function
                if each_user == self._get_user(self.cur_author):
                    user = self.get_user(each_user.id)


        # updates title if it's not there
        song = self.find_song(entry.url)
        if song != None:
            if song.getTitle() == None:
                song.setTitle(player.current_entry.title)
                user.getSong(song).setTitle(player.current_entry.title)
            song.addPlay()

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

    async def on_player_resume(self, entry, **_):
        await self.update_now_playing(entry)

    async def on_player_pause(self, entry, **_):
        await self.update_now_playing(entry, True)

    async def on_player_stop(self, **_):
        await self.update_now_playing()

    async def on_player_finished_playing(self, player, **_):
        # updates our pickles
        if (is_latest_pickle(self.config.auto_playlist_pickle, self.last_modified_ts_apl) == False):
            self.autoplaylist = load_pickle(self.config.auto_playlist_pickle)
        if (is_latest_pickle(self.config.users_list_pickle, self.last_modified_ts_users) == False):
            self.users_list = load_pickle(self.config.users_list_pickle)

        # Clear song that was playing
        player.currently_playing = None
        #reset volume
        player.volume = self.config.default_volume;
        #re-seeds random        
        random.seed()

        if not player.playlist.entries and not player.current_entry and self.config.auto_playlist:
            counter = 0
            while self.autoplaylist and counter < 100 and not player.is_paused:

                playURL = None
                people = []
                #Looking for people in the channel to choose who song gets played
                for m in player.voice_client.channel.voice_members:
                    if not (m.deaf or m.self_deaf or m.id == self.user.id):
                        people.append(m.id)

                print("\nGhost list: ", self.ghost_list)
                print("Past played: %s of %s" % (len(self.list_Played), self.len_list_Played))
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

                author = random.choice(people)
                self.cur_author = author
                print(author)

                song_url = ""

                user = self.get_user(author)
                if user == None:
                    counter = counter + 1
                    continue

                if user.getID() != self.user.id:
                    if len(user.getSongList()) == 0:
                        print("USER HAS NO SONGS IN APL")
                        counter = counter + 1
                        continue
                    else:
                        if self._get_user(author, voice=True) and (self._get_channel(author, voice=True) == self._get_channel(self.user.id, voice=True)):
                            print(self._get_user(author, voice=True))

                            # apparently i dont have the links set up correctly
                            song = random.choice(user.getSongList())
                            song = self.find_song(song.getURL())

                            # if user's mood isn't the default setting (None)
                            if user.getMood() != "" and user.getMood() != None:
                                print("MOOD: ", user.getMood())

                                #song = random.choice(self.dict_moods[author])
                                if user.getMood().lower() in self.metaData.keys():
                                    playURL = random.choice(self.metaData[user.getMood().lower()])
                                    print("PLAYURL: ", playURL)
                                else:
                                    prntStr = "The tag **[" + user.getMood() + "]** does not exist."
                                    return Response(prntStr, delete_after=35)
                            else:
                                song = random.choice(user.getSongList())
                                if song == None:
                                    counter = counter + 1
                                    continue
                                song = self.find_song(song.getURL())

                            #check if repeat song
                            if song.getURL() in self.list_Played:
                                print("Song played too recently")
                                counter = counter + 1
                                continue
                            if len(self.list_Played) >= self.len_list_Played:
                                del self.list_Played[0:(len(self.list_Played) - self.len_list_Played)]
                            if playURL == None:
                                print(song.getTitle())
                                self.list_Played.append(song.getURL())
                            else:
                                print(playURL)
                                self.list_Played.append(playURL)

                            counter = 0
                        else:
                            if list(filter(lambda personID: author in self.ghost_list[personID], self.ghost_list.keys())):
                                print("GHOST IN CHANNEL!")
                                song = random.choice(user.getSongList())
                                song = self.find_song(song.getURL())
                                #check if repeat song
                                if song.getURL() in self.list_Played:
                                    print("Song played too recently")
                                    counter = counter + 1
                                    continue
                                if len(self.list_Played) >= self.len_list_Played:
                                    del self.list_Played[0:(len(self.list_Played) - self.len_list_Played)]
                                self.list_Played.append(song.getURL())
                                counter = 0
                            else:
                                print("USER NOT IN CHANNEL!")
                                print(author)
                                print(TITLE_URL_SEPARATOR)
                                counter = counter + 1
                                continue

                info = None
                try:
                    if playURL == None and song != None:
                        playURL = song.getURL()
                    info = await self.downloader.extract_info(player.playlist.loop, playURL, download=False, process=False)
                except Exception as e:
                    if "Cannot identify player" not in str(e) or "Signature extraction failed" not in str(e):
                        song = self.find_song(playURL)
                        if song != None:
                            await self.notify_likers(song, str(e))
                            self.remove_from_autoplaylist(song.getTitle(), song.getURL())
                            author = self._get_user(user.getID())
                            channel = self._get_channel(author.id)
                            #tags = song.getTags()
                            #for tag in tags:
                            #    await self._cmd_removetag(player, author, channel, tag, printing=False)
                            #this doesn't work because there's currently no song playing.. not sure how to do this
                            self.safe_print("[Info] Removing unplayable song from autoplaylist: %s" % playURL)
                        print("\a")  # BEEPS
                        continue
                    else:
                        print("???")
                        print("ignore")
                        print(e)

                if info is None:
                    print("???")
                    print(author)
                    continue

                if info.get('entries', None):  # or .get('_type', '') == 'playlist'
                    pass  # Wooo playlist
                    # Blarg how do I want to do this

                # TODO: better checks here
                if playURL != None:
                    song = self.find_song(playURL)

                player.currently_playing = song

                # inc play count
                #player.currently_playing.addPlay()

                if player.currently_playing:
                    player.volume = player.currently_playing.getVolume();
                    print("Stored song volume: %s" % player.currently_playing.getVolume())
                try:
                    entry, position = await player.playlist.add_entry(playURL, channel=None, author=None)
                    await self.update_now_playing(entry)
                except exceptions.ExtractionError as e:
                    print("Error adding song from autoplaylist:", e)
                    continue

                break

            if not self.autoplaylist:
                print("[Warning] No playable songs in the autoplaylist, disabling.")
                self.config.auto_playlist = False

    async def on_player_entry_added(self, playlist, entry, **_):
        pass

    async def update_now_playing(self, entry=None, is_paused=False):
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
            game = discord.Game(name=name)

        await self.change_status(game)


    async def safe_send_message(self, dest, content, *, tts=False, expire_in=0, also_delete=None, quiet=False):
        msg = None
        try:
            msg = await self.send_message(dest, content, tts=tts)

            if msg and expire_in:
                asyncio.ensure_future(self._wait_delete_msg(msg, expire_in))

            if also_delete and isinstance(also_delete, discord.Message):
                asyncio.ensure_future(self._wait_delete_msg(also_delete, expire_in))

        except discord.Forbidden:
            if not quiet:
                self.safe_print("Warning: Cannot send message to %s, no permission" % dest.name)

        except discord.NotFound:
            if not quiet:
                self.safe_print("Warning: Cannot send message to %s, invalid channel?" % dest.name)

        return msg

    async def safe_delete_message(self, message, *, quiet=False):
        try:
            return await self.delete_message(message)

        except discord.Forbidden:
            if not quiet:
                self.safe_print("Warning: Cannot delete message \"%s\", no permission" % message.clean_content)

        except discord.NotFound:
            if not quiet:
                self.safe_print("Warning: Cannot delete message \"%s\", message not found" % message.clean_content)

    async def safe_edit_message(self, message, new, *, send_if_fail=False, quiet=False):
        try:
            return await self.edit_message(message, new)

        except discord.NotFound:
            if not quiet:
                self.safe_print("Warning: Cannot edit message \"%s\", message not found" % message.clean_content)
            if send_if_fail:
                if not quiet:
                    print("Sending instead")
                return await self.safe_send_message(message.channel, new)

    def safe_print(self, content, *, end='\n', flush=True):
        sys.stdout.buffer.write((content + end).encode('utf-8', 'replace'))
        if flush: sys.stdout.flush()

    async def send_typing(self, destination):
        try:
            return await super().send_typing(destination)
        except discord.Forbidden:
            if self.config.debug_mode:
                print("Could not send typing to %s, no permission" % destination)

    async def edit_profile(self, **fields):
        if self.user.bot:
            return await super().edit_profile(**fields)
        else:
            return await super().edit_profile(self.config._password,**fields)

    def _cleanup(self):
        try:
            self.loop.run_until_complete(self.logout())
        except: # Can be ignored
            pass

        pending = asyncio.Task.all_tasks()
        gathered = asyncio.gather(*pending)

        try:
            gathered.cancel()
            self.loop.run_until_complete(gathered)
            gathered.exception()
        except: # Can be ignored
            pass

    # noinspection PyMethodOverriding
    def run(self):
        try:
            self.loop.run_until_complete(self.start(*self.config.auth))

        except discord.errors.LoginFailure:
            # Add if token, else
            raise exceptions.HelpfulError(
                "Bot cannot login, bad credentials.",
                "Fix your Email or Password or Token in the options file.  "
                "Remember that each field should be on their own line.")
        except Exception:
            print("Exception consumed")

        finally:
            try:
                self._cleanup()
            except Exception as e:
                print("Error in cleanup:", e)

            self.loop.close()
            if self.exit_signal:
                raise self.exit_signal

    async def logout(self):
        await self.disconnect_all_voice_clients()
        return await super().logout()

    async def on_error(self, event, *args, **kwargs):
        ex_type, ex, stack = sys.exc_info()

        if ex_type == exceptions.HelpfulError:
            print("Exception in", event)
            print(ex.message)

            await asyncio.sleep(2)  # don't ask
            await self.logout()

        elif issubclass(ex_type, exceptions.Signal):
            self.exit_signal = ex_type
            await self.logout()

        else:
            traceback.print_exc()

    async def on_resumed(self):
        for vc in self.the_voice_clients.values():
            vc.main_ws = self.ws

    async def on_ready(self):
        print('\rConnected!  Musicbot v%s\n' % BOTVERSION)

        if self.config.owner_id == self.user.id:
            raise exceptions.HelpfulError(
                "Your OwnerID is incorrect or you've used the wrong credentials.",

                "The bot needs its own account to function.  "
                "The OwnerID is the id of the owner, not the bot.  "
                "Figure out which one is which and use the correct information.")

        self.init_ok = True

        self.safe_print("Bot:   %s/%s#%s" % (self.user.id, self.user.name, self.user.discriminator))

        owner = self._get_owner(voice=True) or self._get_owner()
        if owner and self.servers:
            self.safe_print("Owner: %s/%s#%s\n" % (owner.id, owner.name, owner.discriminator))

            print('Server List:')
            [self.safe_print(' - ' + s.name) for s in self.servers]

        elif self.servers:
            print("Owner could not be found on any server (id: %s)\n" % self.config.owner_id)

            print('Server List:')
            [self.safe_print(' - ' + s.name) for s in self.servers]

        else:
            print("Owner unknown, bot is not on any servers.")
            if self.user.bot:
                print("\nTo make the bot join a server, paste this link in your browser.")
                print("Note: You should be logged into your main account and have \n"
                      "manage server permissions on the server you want the bot to join.\n")
                print("    " + await self.generate_invite_link())

        print()

        if self.config.bound_channels:
            chlist = set(self.get_channel(i) for i in self.config.bound_channels if i)
            chlist.discard(None)
            invalids = set()

            invalids.update(c for c in chlist if c.type == discord.ChannelType.voice)
            chlist.difference_update(invalids)
            self.config.bound_channels.difference_update(invalids)

            print("Bound to text channels:")
            [self.safe_print(' - %s/%s' % (ch.server.name.strip(), ch.name.strip())) for ch in chlist if ch]

            if invalids and self.config.debug_mode:
                print("\nNot binding to voice channels:")
                [self.safe_print(' - %s/%s' % (ch.server.name.strip(), ch.name.strip())) for ch in invalids if ch]

            print()

        else:
            print("Not bound to any text channels")

        if self.config.autojoin_channels:
            chlist = set(self.get_channel(i) for i in self.config.autojoin_channels if i)
            chlist.discard(None)
            invalids = set()

            invalids.update(c for c in chlist if c.type == discord.ChannelType.text)
            chlist.difference_update(invalids)
            self.config.autojoin_channels.difference_update(invalids)

            print("Autojoining voice chanels:")
            [self.safe_print(' - %s/%s' % (ch.server.name.strip(), ch.name.strip())) for ch in chlist if ch]

            if invalids and self.config.debug_mode:
                print("\nCannot join text channels:")
                [self.safe_print(' - %s/%s' % (ch.server.name.strip(), ch.name.strip())) for ch in invalids if ch]

            autojoin_channels = chlist

        else:
            print("Not autojoining any voice channels")
            autojoin_channels = set()

        print()
        print("Options:")

        self.safe_print("  Command prefix: " + self.config.command_prefix)
        print("  Default volume: %s%%" % int(self.config.default_volume * 100))
        print("  Skip threshold: %s votes or %s%%" % (
            self.config.skips_required, self._fixg(self.config.skip_ratio_required * 100)))
        print("  Now Playing @mentions: " + ['Disabled', 'Enabled'][self.config.now_playing_mentions])
        print("  Auto-Summon: " + ['Disabled', 'Enabled'][self.config.auto_summon])
        print("  Auto-Playlist: " + ['Disabled', 'Enabled'][self.config.auto_playlist])
        print("  Auto-Pause: " + ['Disabled', 'Enabled'][self.config.auto_pause])
        print("  Delete Messages: " + ['Disabled', 'Enabled'][self.config.delete_messages])
        if self.config.delete_messages:
            print("    Delete Invoking: " + ['Disabled', 'Enabled'][self.config.delete_invoking])
        print("  Debug Mode: " + ['Disabled', 'Enabled'][self.config.debug_mode])
        print("  Downloaded songs will be %s" % ['deleted', 'saved'][self.config.save_videos])
        print()

        # maybe option to leave the ownerid blank and generate a random command for the owner to use
        # wait_for_message is pretty neato

        if not self.config.save_videos and os.path.isdir(AUDIO_CACHE_PATH):
            if self._delete_old_audiocache():
                print("Deleting old audio cache")
            else:
                print("Could not delete old audio cache, moving on.")

        if self.config.autojoin_channels:
            await self._autojoin_channels(autojoin_channels)

        elif self.config.auto_summon:
            print("Attempting to autosummon...", flush=True)

            # waitfor + get value
            owner_vc = await self._auto_summon()

            if owner_vc:
                print("Done!", flush=True)  # TODO: Change this to "Joined server/channel"
                if self.config.auto_playlist:
                    print("Starting auto-playlist")
                    await self.on_player_finished_playing(await self.get_player(owner_vc))
            else:
                print("Owner not found in a voice channel, could not autosummon.")

        print()
        # t-t-th-th-that's all folks!

    def fetch_title(self, song_line):

        if TITLE_URL_SEPARATOR in song_line:
            (title, url_likers) = song_line.split(TITLE_URL_SEPARATOR)
            return title
        else:
            return None

    def fetch_url(self, song_line):

        if TITLE_URL_SEPARATOR in song_line:
            (title, url_likers) = song_line.split(TITLE_URL_SEPARATOR)
        else:
            # now we know the format of song_line
            url_likers = song_line

        if URL_LIKERS_SEPARATOR in url_likers:
            (url, likers) = url_likers.split(URL_LIKERS_SEPARATOR)
            return url
        elif ", " in url_likers:
            (url, likers) = url_likers.split(", ")
            return url
        else:
            return url_likers

    def fetch_likers(self, song_line):

        if TITLE_URL_SEPARATOR in song_line:
            (title, url_likers) = song_line.split(TITLE_URL_SEPARATOR)
        else:
            url_likers = song_line

        if URL_LIKERS_SEPARATOR in url_likers:
            (url, likers) = url_likers.split(URL_LIKERS_SEPARATOR)
        elif ", " in url_likers:
            (url, likers) = url_likers.split(", ")
        else:
            likers = None

        return likers

    def get_likers(self, song_url):
        likers = []

        for each_song in self.autoplaylist:
            if each_song != None:
                if each_song.getURL() == song_url:
                    likers = each_song.getLikers()

        return self._get_likers(likers)

    # takes a list of ids, returns a list of usernames
    def _get_likers(self, likers):

        names = []
        for each_id in likers:
            name = self._get_user(each_id)
            # what if the user has left the server?
            if name is not None:
                names.append(name)

        return names

    def add_to_autoplaylist(self, title, url, author=None):

        if (is_latest_pickle(self.config.auto_playlist_pickle, self.last_modified_ts_apl) == False):
            self.autoplaylist = load_pickle(self.config.auto_playlist_pickle)

        if author == None:
            print("No Author... Don't know who to add to")
            return False

        if not author.isnumeric():
            author = author.id

        song = self.find_song(url)

        # if not on anyone's list, let's add it to someone's
        if song == None:
            song = Music(title, url, author)
            self.autoplaylist.append(song)
        # otherwise we just want to add this liker to the list
        else:
            if song.hasLiker(author):
                print("Song already added", url)
                return False
            else:
                # appends current author to the end of the likers list
                song.addLiker(author)

        self._add_to_autoplaylist(title, url, author)

        if (is_latest_pickle(self.config.auto_playlist_pickle, self.last_modified_ts_apl) == False):
            self.last_modified_ts_apl = store_pickle(self.config.auto_playlist_pickle, self.autoplaylist)
        return True

    def _add_to_autoplaylist(self, title, url, author=None):


        if (is_latest_pickle(self.config.users_list_pickle, self.last_modified_ts_users) == False):
            self.users_list = load_pickle(self.config.users_list_pickle)

        if author == None:
            song = self.find_song(url)
            if song == None:
                # song not in our APL yet
                self.add_to_autoplaylist(title, url, author)

            # trying to grab the likers from the apl
            likers = song.getLikers()
            if likers == None:
                print("Really don't know who to add to!")
                return
            else:
                for liker in likers:
                    author = self._get_user(liker)
                    self._add_autoplaylist(title, url, author)
                    return

        user = self.get_user(author)

        # if a user doesn't exist, we add them
        if user == None:
            if not author.isnumeric():
                author = author.id

            user = User(author)
            self.users_list.append(user)

        music_obj = self.find_song(url)

        # add a new music obj and tries again (this should never fail unless _add_to_autoplaylist was explicitly called)
        if music_obj == None:
            music_obj = Music(title, url, author)
            self.add_to_autoplaylist(title, url, author)
            return

        if not user.hasSong(music_obj):
            user.addSong(music_obj)

        if (is_latest_pickle(self.config.users_list_pickle, self.last_modified_ts_users) == False):
            self.last_modified_ts_users = store_pickle(self.config.users_list_pickle, self.users_list)

    def remove_from_autoplaylist(self, title, url, author=None):

        if (is_latest_pickle(self.config.auto_playlist_pickle, self.last_modified_ts_apl) == False):
            self.autoplaylist = load_pickle(self.config.auto_playlist_pickle)

        if author == None:
            #check if we can grab the likers from the apl
            song = self.find_song(url)
            if song != None:
                if len(song.getLikers()) == 0:
                    return False
                else:
                    for each_liker in song.getLikers():
                        self.remove_from_autoplaylist(title, url, each_liker)
                    return True
            else:
                print("No Author... Don't know who to remove from")
                return False

        if not str(author).isnumeric():
            author = author.id

        song = self.find_song(url)

        if song != None:

            if not song.hasLiker(author):
                print("Hey! You can't remove a song that's not even yours!")
                return False

            if len(song.getLikers()) > 1:
                #self.autoplaylist[song_index].removeLiker(author)
                song.removeLiker(author)
            elif len(song.getLikers()) == 1:
                print("ONE LIKER, REMOVING: ", song.getTitle())
                self.autoplaylist.remove(song)
            else:
                print("NO LIKERS, NOT REMOVING: ", song.getTitle())
                return False

            if (is_latest_pickle(self.config.auto_playlist_pickle, self.last_modified_ts_apl) == False):
                self.last_modified_apl = store_pickle(self.config.auto_playlist_pickle, self.autoplaylist)
            return self._remove_from_autoplaylist(title, url, author)

        else:
            print("Can't remove a song that's not in the auto playlist")
            return False

    # removes from our dictionary of lists
    def _remove_from_autoplaylist(self, title, url, author=None):

        if (is_latest_pickle(self.config.users_list_pickle, self.last_modified_ts_users) == False):
            self.users_list = load_pickle(self.config.users_list_pickle)

        if author == None:
            likers = song.getLikers()
            for liker in likers:
                author = self._get_user(liker)
                self._remove_autoplaylist(song, author)
                #idk how to handle the return :/
                return True

        user = self.get_user(author)

        if user == None:
            print("User is not in our server, can't remove from your list!")
            return False

        song = self.find_song(url)
        if song == None:
            song = Music(title, url, author)
            print("Just a heads up, this isn't in our APL.")
            #return False

        if user.hasSong(song):
            user.removeSong(song)
        else:
            print("The song isn't in the user's personal list")
            return False

        if (is_latest_pickle(self.config.users_list_pickle, self.last_modified_ts_users) == False):
            self.last_modified_ts_users = store_pickle(self.config.users_list_pickle, self.users_list)
        return True

    # finds the first instance a song URL is found or if a string is found in a title and returns the object
    def find_song(self, args):

        # forcing strings here

        for each_song in self.autoplaylist:

            if args == each_song.getURL():
                return each_song

            if each_song.getTitle() != None:
                if args in each_song.getTitle().lower():
                    return each_song
        return None

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
            if cmd:
                return Response(
                    "```\n{}```".format(
                        dedent(cmd.__doc__),
                        command_prefix=self.config.command_prefix
                    ),
                    delete_after=60
                )
            else:
                return Response("No such command", delete_after=10)

        else:
            helpmsg = "**Commands**\n```"
            commands = []

            for att in dir(self):
                if att.startswith('cmd_') and att != 'cmd_help':
                    command_name = att.replace('cmd_', '').lower()
                    commands.append("{}{}".format(self.config.command_prefix, command_name))

            helpmsg += ", ".join(commands)
            helpmsg += "```"
            helpmsg += "https://github.com/SexualRhinoceros/MusicBot/wiki/Commands-list"

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
                "Bot accounts can't use invite links!  Click here to invite me: \n{}".format(url),
                reply=True, delete_after=30
            )

        try:
            if server_link:
                await self.accept_invite(server_link)
                return Response(":+1:")

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
        curMood = "none"

        # fetches user from self.users_list
        user = self.get_user(author.id)

        if (args is ""):

            # if their mood isn't default
            if user.getMood() != "":
                # search for which moods were added
                for tag in list(self.metaData.keys()):
                    if user.hasMood(tag):
                        curMood = tag

            longStr = "**" + author.name + "**, your current mood is: **" + curMood + "**"
        elif "reset" in args:
            user.addMood("")
            longStr = "**" + author.name + "**, your mood has been reset and your autoplaylist has been restored."
        elif args in str(list(self.metaData.keys())):
            user.addMood(args)
            longStr = "**" + author.name + "**, your mood is set to: **" + args + "**"
        else:
            longStr = "Error: We could not find the tag: ", args, "\nTry using \"~tag list\" to see available tags."

        return Response(longStr, delete_after=35)

    async def cmd_trackcount(self, server, player, channel, author, leftover_args):
        """
        Usage:
        {command_prefix}trackcount #

        Adjusts the amount of songs that need to be played before a previous song can be played again

        """

        if len(leftover_args) > 1:
            prntStr = "Too many arguments given for **adjrepeat** command."
            return Response(prntStr, delete_after=20)
        elif len(leftover_args) == 0:
            prntStr = "Current allowed number of repeated songs is **" + str(self.len_list_Played) + "**."
            return Response(prntStr, delete_after=20)
        try:
            self.len_list_Played = int(leftover_args[0])
            prntStr = "Allowed number of repeated song changed to **" + leftover_args[0] + "**."
        except:
            prntStr = "Invalid value given. Please input a number."
        return Response(prntStr, delete_after=20)

    async def cmd_stat(self, server, player, channel, author, leftover_args):
        """
        Usage:
        {command_prefix}stat
        {command_prefix}stat compat

        Prints the number of songs for the top 10 and the author who asked
        Prints the amount of similar songs to the other people in the discord

        """
        if len(leftover_args) > 0:
            if leftover_args[0].strip().lower() == "compat":
                return await self._cmd_compat(server, player, channel, author)
        listNumbers = {}
        longStr = ""

        await self.send_typing(channel)
        #Get ids of all users
        #(m.name, m.id) for m in server.members
        for m in server.members:
            #print("Process: " + m.name + " : " + str(m.id))
            user = self.get_user(m.id)
            if user != None:
                listNumbers[m.name] = len(user.getSongList())
            else:
                #print("skipped")
                pass

        #Printing the users song number
        if author.name in list(listNumbers.keys()):
            longStr += "`" + str(author)[:-5] + ": " + str(listNumbers[str(author)[:-5]]) + "`\n\n"
        else:
            print("A. " + author.id)
            print("B. " + str(listNumbers.keys()))
            longStr += "`" + str(author)[:-5] + ": 0`\n\n"
        longStr += "*--Number of Songs--*\n"
        for i in range(0,10):
            #gets the key with the largest value
            tempLarge = max(listNumbers.items(), key=lambda k: k[1])
            #delete to find next max
            del listNumbers[tempLarge[0]]
            tempStr = str(i + 1) + "." + str(tempLarge[0]) + ": " + str(tempLarge[1])
            #If the person asked for it their name is bold
            if tempLarge[0] == str(author)[:-5]:
                tempStr = "**__" + tempStr + "__**"
            longStr += tempStr + "\n"
            if len(listNumbers) == 0:
                break

        return Response(longStr, delete_after=35)


    async def _cmd_compat(self, server, player, channel, author):
        #Expended functions on stat
        #   - compat

        t0 = time.clock()
        #If author no music printing
        user = self.get_user(author.id)
        if user == None:
            prntStr = "You have no music"
            return Response(prntStr, delete_after=35)

        # Updated #
        prntStr = "**__Affinity to Others__**\n\n"
        similarSongs = {}
        #Goes through each song
        for songObj in self.autoplaylist:
            #If you liked
            if author.id in songObj.getLikers():
                likeList = songObj.getLikers()
                for liker in likeList:
                    if liker in similarSongs:
                        similarSongs[liker] += 1
                    else:
                        similarSongs[liker] = 1

        prntStr += "Total Common Songs: **" + str(sum(similarSongs.values()) - len(user.getSongList())) + "**\n\n"
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
                prntStr += ": *" + str(ID_NUM[1]) + " of " + str(len(user.getSongList())) + "*\n"

        print("Time to process compat: " + str(time.clock() - t0) + " sec")
        return Response(prntStr, delete_after=35)
        ###########

        '''
        OLD WAY
        user_index = getUserIndex(author.id)
        if user_index == None:
        user = self.get_user(author.id)
        if user == None:
            prntStr = "You have no music"
            return Response(prntStr, delete_after=35)

        #List of people with similar songs
        peopleCompare = {}
        prntStr = "**__Affinity to Others__**\n\n"

        #Finds each link for the author who called command
        for link in self.users_list[user_index]:
            #Gets the people who liked the url
            listOfPeople = self.get_likers(link)
            for person in listOfPeople:
                if person in peopleCompare:
                    peopleCompare[person] += 1
                else:
                    peopleCompare[person] = 1
        #Organizes the list from largest to smallest
        for i in range(0,len(peopleCompare.keys())):
            pplInfo = max(peopleCompare.items(), key=lambda k: k[1])
            del peopleCompare[pplInfo[0]]
            if pplInfo[0].id != author.id:
                prntStr += pplInfo[0].name + ": *" + str(pplInfo[1]) + " of " + str(len(self.users_list[author.id])) + "*\n"
        print("Time to process compat: " + str(time.clock() - t0) + " sec")
        return Response(prntStr, delete_after=35)
        '''

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


    async def cmd_tag(self, player, author, channel, permissions, leftover_args):
        """
        Usage:
            {command_prefix}tag [command] the_tag

        Ex: ~tag add rock
        [command]:
        - ADD : Adds the current song to the specified tag
        - REMOVE : Removes the current song from the specified tag
        - PLAY : Plays a random song from the specified tag
        - LIST : Prints all the tags
        - SHOW : Shows the songs in the specified tag
        - MSG : Messages user with all the songs w/ urls of the specified tag
        """

        await self.send_typing(channel)
        if len(leftover_args) >= 1 and len(leftover_args) <= 2:
            self.updateMetaData()
            if leftover_args[0].lower() == "add":
                return await self._cmd_addtag(player, author, channel, leftover_args[1])
            elif leftover_args[0].lower() == "remove":
                return await self._cmd_removetag(player, author, channel, leftover_args[1])
            elif leftover_args[0].lower() == "play":
                return await self._cmd_playtag(player, author, channel, permissions, leftover_args[1])
            elif leftover_args[0].lower() == "list":
                return await self._cmd_listtag(player, author, channel, permissions, None)
            elif leftover_args[0].lower() == "show":
                return await self._cmd_showtag(player, author, channel, permissions, leftover_args[1])
            elif leftover_args[0].lower() == "msg":
                return await self._cmd_msgtag(player, author, channel, permissions, leftover_args[1])
            else:
                prntStr = "**[" + leftover_args[0] + "]** is not a recognized command"
                return Response(prntStr, delete_after=20)
        else:
            prntStr = "**" + str(len(leftover_args)) + "** arguments were given **1-2** arguments expected"
            return Response(prntStr, delete_after=20)


    async def _cmd_addtag(self, player, author, channel, leftover_args):
        """
        Usage:
            {command_prefix}addtag TAG

        Adds the playing song to the specified tag
        """

        #Checks if tag already exists
        if leftover_args.lower() in self.metaData.keys():
            #Checks if the song is already in the tag/list
            if sanitize_string(player.current_entry.url) not in self.metaData[leftover_args.lower()]:
                self.metaData[leftover_args.lower()].append(player.current_entry.url)
            else:
                prntStr = "**" + player.current_entry.title + "** is already added to the **[" + leftover_args + "]** tag"
                return Response(prntStr, delete_after=20)
        else:
            #If tag doesn't exist, create a new tag
            self.metaData[leftover_args.lower()] = [player.current_entry.url]
        #Updating list to file
        await self._cmd_updatetags()
        prntStr = "**" + player.current_entry.title + "** was added to the **[" + leftover_args + "]** tag"
        return Response(prntStr, delete_after=20)

    async def _cmd_removetag(self, player, author, channel, leftover_args, printing=True):
        """
        Usage:
            {command_prefix}removetag TAG

        Removes the current playing song for the specified tag
        """

        # Checks if the tag exists first
        if leftover_args.lower() in self.metaData.keys():
            #Checks if the url is in the list
            if sanitize_string(player.current_entry.url) in self.metaData[leftover_args.lower()]:
                self.metaData[leftover_args.lower()].remove(sanitize_string(player.current_entry.url))
                #Remove tag entirely if empty
                if len(self.metaData[leftover_args.lower()]) == 0:
                    del self.metaData[leftover_args.lower()]
                #Update tags file
                await self._cmd_updatetags()
                prntStr = "**" + player.current_entry.title + "** is removed from **[" + leftover_args + "]** tag"
            else:
                prntStr = "**" + player.current_entry.title + "** was not in **[" + leftover_args + "]** tag"

        if printing == True:
            return Response(prntStr, delete_after=20)
        else:
            return True

    async def _cmd_updatetags(self):
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
            str_to_write.append(sanitize_string(self.metaData[metaTag]))
        write_file(self.config.metadata_file, str_to_write)
        #if (is_latest_pickle == True):
            #self.last_modified_ts = store_pickle(self.config.metadata_file, self.metaData)

    async def _cmd_playtag(self, player, author, channel, permissions, leftover_args):
        """
        Usage:
            {command_prefix}playtag TAG

        Plays a song from the specified tag
        """

        #Checks if tag exists
        if leftover_args.lower() in self.metaData.keys():
            playUrl = random.choice(self.metaData[leftover_args.lower()])
        else:
            prntStr = "The tag **[" + leftover_args + "]** does not exist."
            return Response(prntStr, delete_after=35)
        try:
            info = await self.downloader.extract_info(player.playlist.loop, playUrl, download=False, process=False)
            if not info:
                raise exceptions.CommandError("That video cannot be played.", expire_in=30)
            entry, position = await player.playlist.add_entry(playUrl, channel=channel, author=author)
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
            prntStr = "A song from **[" + leftover_args + "]** was unable to be added."
            return Response(prntStr, delete_after=35)

    async def _cmd_listtag(self, player, author, channel, permissions, leftover_args):
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
        for key,value in sorted(self.metaData.items()):
        #for tags in self.metaData.keys():
            if len(prntStr + key) < 1990:
                prntStr += "**[" + key.lower() + "]** : " + str(len(value)) + "\n"
            else:
                prntStr += "```Partial```"
                break
        return Response(prntStr, delete_after=30)

    async def _cmd_showtag(self, player, author, channel, permissions, leftover_args):
        """
        Usage:
            {command_prefix}showtag TAG

        Shows the songs in a tag
        """

        #Checks if tag exists
        if leftover_args.lower() in self.metaData.keys():
            playUrl = random.choice(self.metaData[leftover_args.lower()])
        else:
            prntStr = "The tag **[" + leftover_args + "]** does not exist."
            return Response(prntStr, delete_after=35)

        prntStr = "__Songs in **[" + leftover_args.capitalize() + "]** tag__\n\n"
        for link in self.metaData[leftover_args]:
            t0 = time.clock()
            #Getting people with the url in their list
            prsnLists = list(filter(lambda person: [song for song in person.getSongList() if link == song.getURL()], self.users_list))
            #prsnLists = []
            #for person in self.users_list:
            #    for song in person.getSongList():
            #        if link == song.getURL():
            #            prsnLists.append(person)

            if len(prsnLists) == 0:
                continue
            #Getting song name
            #print(prsnLists[0].getSongList())
            song = list(filter(lambda songs: link in songs.getURL(), prsnLists[0].getSongList()))

            if len(song) == 0:
                continue

            if len(prntStr + str(song[0])) < 2000:
                if song[0].getTitle() != None:
                    prntStr += ":notes:" + song[0].getTitle() + "\n"
                else:
                    prntStr += ":notes:" + "[NO TITLE] " + song[0].getURL() + "\n"

        return Response(prntStr, delete_after=50)

    async def _cmd_msgtag(self, player, author, channel, permissions, leftover_args):
        """
        Usage:
            {command_prefix}msgtag the_tag

        Messages all the songs and urls in a tag
        """

        #Checks if tag exists
        if leftover_args.lower() in self.metaData.keys():
            playUrl = random.choice(self.metaData[leftover_args.lower()])
        else:
            prntStr = "The tag **[" + leftover_args + "]** does not exist."
            return Response(prntStr, delete_after=35)

        prntStr = []
        for link in self.metaData[leftover_args]:
            t0 = time.clock()
            prsnLists = list(filter(lambda person: [songList for songList in self.users_list[person] if link in songList], self.users_list.keys()))

            songTitle = list(filter(lambda songs: link in songs, self.users_list[prsnLists[0]]))
            if len(songTitle) == 0:
                continue
            prntStr.append(songTitle[0].split(TITLE_URL_SEPARATOR)[0] + "\r\n\t" + link)

        with BytesIO() as prntDoc:
            prntDoc.writelines(d.encode('utf8') + b'\n' for d in prntStr)
            prntDoc.seek(0)
            await self.send_file(author, prntDoc, filename='%stagList.txt' %leftover_args)

        return Response(":mailbox_with_mail:", delete_after=20)

    async def cmd_listhas(self, player, author, channel, permissions, leftover_args):
        """
        Usage:
            {command_prefix}listhas songTitle

        Looks if a song title is in your or others lists

        """

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
            ContainsList = await self.findSongsWithTitle(leftover_args, self.autoplaylist)
            songsInList = len(ContainsList)
            peopleListSongs = {}
            #sorting into a list for each person who liked the songs
            for songObj in ContainsList:
                for person in songObj.getLikers():
                    if person not in peopleListSongs:
                        peopleListSongs[person] = [songObj]
                    else:
                        peopleListSongs[person].append(songObj)

            prntStr = "**Autoplay lists containing: \""
            for word in leftover_args:
                prntStr += word.strip() + " "
            prntStr = prntStr.strip() + "\"**\n"
            #Check if the 'command' asker has songs
            if author.id in peopleListSongs:
                prsnPrint = "\n\t:busts_in_silhouette:__Yours__\n"
                for songObj in peopleListSongs[author.id]:
                    prsnPrint += ":point_right:" + songObj.getTitle() + "(" + songObj.getURL() + ")" + "\n"
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
                prsnPrint = "\n\t:busts_in_silhouette:__" + userName + "__\n"
                for songObj in peopleListSongs[person]:
                    prsnPrint += ":point_right:" + songObj.getTitle() + "(" + songObj.getURL() + ")" + "\n"
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

            #######################
            '''
            prntStr = ""
            toPlay = None
            searchWord = ""
            #Combining all search words
            if leftover_args[0] == "-w":
                for words in leftover_args[1:]:
                    searchWord += words + " "
                searchWord = " " + searchWord.lower()
            elif "-p" in leftover_args[0]:
                 for words in leftover_args[1:]:
                     searchWord += words + " "
                 searchWord = searchWord.strip().lower()
                 toPlay = leftover_args[0].split("-p")[1]
                 if toPlay == "":
                     toPlay = 1
            else:
                for words in leftover_args:
                    searchWord += words + " "
                searchWord = searchWord.strip().lower()
            prntStr += "**Autoplay lists containing: \"" + searchWord + "\"**\n\n"
            t0 = time.clock()

            user = self.get_user(author.id)
            if user == None:
                print("NULL USER")
                return

            #Gets all songs with the input word in your list
            #ContainsList = list(filter(lambda element: searchWord in element.getTitle(), user.getSongList()))
            ContainsList = []
            for element in user.getSongList():
                if element.getTitle() != None:
                    if searchWord.lower() in element.getTitle().lower():
                        ContainsList.append(element)
            print("Time pass on your list: %s", time.clock() - t0)
            #Removing unprocessed songs
            for song in ContainsList:
                if song.getTitle() == None:
                    ContainsList.remove(link)
            prsnPrint = "\t\t:busts_in_silhouette:__Yours__\n"
            #Printing the list with the word
            for song in ContainsList:
                #Making the song list
                try:
                    title = song.getTitle()
                    link = song.getURL()
                    prsnPrint += ":point_right:" + title + " (" + link + ")" + "\n"
                except:
                    print("Fail to parse yours: " + link)
                    ContainsList.remove(link)
                    continue
                #Dealing with -p command
                try:
                    if (ContainsList.index(link) + 1) == int(toPlay):
                        #await self.cmd_play(player, channel, author, permissions, "", link.split(" --- ")[1])
                        info = await self.downloader.extract_info(player.playlist.loop, link.split(TITLE_URL_SEPARATOR)[1], download=False, process=False)
                        if not info:
                            raise exceptions.CommandError("That video cannot be played.", expire_in=30)
                        entry, position = await player.playlist.add_entry(link.split(TITLE_URL_SEPARATOR)[1], channel=channel, author=author)
                        #Not sure if needed
                        #await entry.get_ready_future()
                        if position == 1 and player.is_stopped:
                            position = 'Up next!'
                        else:
                            try:
                                time_until = await player.playlist.estimate_time_until(position, player)
                            except:
                                time_until = ''
                        shrtPrint = "Enqueued **%s** to be played. Position in queue: %s - estimated time until playing: %s" %(entry.title, position, time_until)
                        await self.safe_send_message(channel, shrtPrint, expire_in=30)
                except Exception:
                    pass
            #Getting number of songs added
            songsInList += len(ContainsList)
            if ContainsList:
                prntStr += prsnPrint + "\n"

            #Looking in other peoples lists for the song
            t0 = time.clock()
            for each_user in self.users_list:
                #If the key being looked at isn't the same as the author
                if each_user.getID() != author.id:
                    userName = self._get_user(each_user.getID())
                    #Converting the name accordinly (if user doesn't exist anymore)
                    userName = "Unknown User" if str(userName) == "None" else str(userName)[:-5]
                    ContainsList = []
                    for element in each_user.getSongList():
                        if element.getTitle() != None:
                            if searchWord.lower() in element.getTitle().lower():
                                ContainsList.append(element)
                    for song in ContainsList:
                        if song.getTitle() == None:
                            ContainsList.remove(song)
                    prsnPrint += "\t\t:busts_in_silhouette:__" + userName + "__\n"
                    #Prints other peoples list
                    for song in ContainsList:
                        try:
                            title = song.getTitle()
                            link = song.getURL()
                            prsnPrint += ":point_right:" + title + " (" + link + ")" + "\n"
                        except:
                            print("Fail to parse " + userName + ": " + link)
                            ContainsList.remove(song)
                            pass
                    #Number of songs added
                    songsInList += len(ContainsList)
                    if ContainsList:
                        prntStr += prsnPrint + "\n"
                    prsnPrint = ""
            print("Time pass on others list: %s", time.clock() - t0)

            #PRINTING TIME
            #Print string limit 2000, go into special printing
            await self.safe_delete_message(thinkingMsg)
            if len(prntStr) > 2000:
                #Splits into each person
                eachPersonList = prntStr.split("\t\t")
                #Prints the inital line
                await self.send_typing(channel)
                await self.safe_send_message(channel, eachPersonList[0], expire_in=(0.1*songsInList+5))
                del eachPersonList[0]
                print("ppl: " + str(len(eachPersonList)) + " - # of songs " + str(songsInList))
                toPrintStr = ""
                for prsnList in eachPersonList:
                    #Prints abbrivated version of list
                    #Note: another option is to print without urls
                    if len(prsnList) > 2000:
                        [firstHalf, secondHalf] = prsnList.split("__\n")
                        secondHalfList = secondHalf.split(":point_right:")
                        secondHalf = secondHalfList[0]
                        del secondHalfList[0]
                        while (len(secondHalf) + len(":point_right:") + len(secondHalfList[0])) < 1905:
                            secondHalf += ":point_right:" + secondHalfList[0]
                            del secondHalfList[0]
                        prntLn = "```Partial List: " + firstHalf[23:] + "```\n" + secondHalf
                        await self.send_typing(channel)
                        await self.safe_send_message(channel, prntLn, expire_in=(0.1*songsInList+5))
                    #If adding next person list to current too large, print
                    elif (len(toPrintStr) + len(prsnList) > 2000):
                        await self.send_typing(channel)
                        await self.safe_send_message(channel, toPrintStr, expire_in=(0.1*songsInList+5))
                        toPrintStr = prsnList
                    #Can add person's list to printing queue
                    else:
                        toPrintStr += prsnList
                if len(toPrintStr) != 0:
                    await self.send_typing(channel)
                    await self.safe_send_message(channel, toPrintStr, expire_in=(0.1*songsInList+5))
                return
        return Response(prntStr, delete_after=(1.1*songsInList+50))
        '''

    async def findSongsWithTitle(self, searchWords, searchList=None):
        """
            Finds the object songs with the title matching all the words

            Recurssive function going till searchWords is empty
            searchWords - array of words looking for
            searchList - list being looked in for each word
        """
        foundSongs = []
        # print("Looking for " + searchWords[0])
        for songObj in searchList:
            if songObj.getTitle() == None:
                continue
            if searchWords[0].strip().lower() in songObj.getTitle().lower():
                foundSongs.append(songObj)
        # print(foundSongs)
        if (len(searchWords) == 1):
            return foundSongs
        return await self.findSongsWithTitle(searchWords[1:], foundSongs)

    async def cmd_mylist(self, player, channel, author, permissions, leftover_args):
        """
        Usage:
            {command_prefix}mylist

        View the songs in your personal autoplaylist.
        """

        data = []

        user = self.get_user(author.id)
        if user != None:
            for song in user.getSongList():
                # yikes
                song = self.find_song(song.getURL())
                if (song != None):
                    data.append(str(song) + ", Playcount: " + str(song.getPlays()) + "\r\n")

            if len(user.getSongList()) == 0:
                data.append("Your auto playlist is empty.")

            # sorts the mylist alphabetically Note: only works for ASCII characters
            data.sort(key=str.lower)

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

        #print("CMD_LIKE ", str(author.id))
        #print(self.users_list)

        if self.add_to_autoplaylist(player.current_entry.title, player.current_entry.url, author.id):
            reply_text = "**%s**, the song **%s** has been added to your auto playlist."
        else:
            reply_text = "**%s**, this song **%s** is already added to your auto playlist."

        user = str(author)[:-5]
        song_name = player.current_entry.title

        #print(self.users_list)

        reply_text %= (user, song_name)

        return Response(reply_text, delete_after=30)

    async def cmd_dislike(self, player, channel, author, permissions, leftover_args, song_url=None):
        """
        Usage:
            {command_prefix}dislike
            {command_prefix}dislike song_url
            {command_prefix}dislike queue_position

        Removes the current song from your autoplaylist.
        """

        reply_text = ""
        user = ""

        if song_url is None:
            url = player.current_entry.url
            title = player.current_entry.title
        elif song_url.isnumeric():
            position = int(song_url)
            entry = await player.playlist.get_entry(position)

            if entry is None:
                url = player.current_entry.url
                title = player.current_entry.url
            else:
                url = entry.url
                title = entry.title
        else:
            url = song_url
            cached_song = self.find_song(url)
            if cached_song != None:
                title = cached_song.getTitle()
            else:
                title = None;

        if self.remove_from_autoplaylist(title, url, author.id):
            reply_text = "**%s**, the song **%s** has been removed from your auto playlist."
            player.current_entry.disliked = True
        else:
            reply_text = "**%s**, the song **%s** wasn't in your auto playlist or something went wrong."

        user = str(author)[:-5]

        if title is None:
            title = player.current_entry.title

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
        except ValueError as e:
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
            position = len(player.playlist.entries)

        reply_text %= (btext, position+1)

        return Response(reply_text, delete_after=30)

    async def cmd_play(self, player, channel, author, permissions, leftover_args, song_url):
        """
        Usage:
            {command_prefix}play song_link
            {command_prefix}play text to search for

        Adds the song to the playlist.  If a link is not provided, the first
        result from a youtube search is added to the queue.
        """

        song_url = song_url.strip('<>')

        if permissions.max_songs and player.playlist.count_for_user(author) >= permissions.max_songs:
            raise exceptions.PermissionsError(
                "You have reached your enqueued song limit (%s)" % permissions.max_songs, expire_in=30
            )

        await self.send_typing(channel)


        if leftover_args:
            song_url = ' '.join([song_url, *leftover_args])

        # let's see if we already have this song or a similar one. i feel like this will help 70% of the time
        # let's check the songs the user likes before looking at other people's

        temp_url = await self.check_songs(song_url, author)
        if temp_url != None:
            song_url = temp_url

        try:
            info = await self.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
        except Exception as e:
            raise exceptions.CommandError(e, expire_in=30)

        if not info:
            raise exceptions.CommandError("That video cannot be played.", expire_in=30)

        # abstract the search handling away from the user
        # our ytdl options allow us to use search strings as input urls
        if info.get('url', '').startswith('ytsearch'):
            # print("[Command:play] Searching for \"%s\"" % song_url)
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
                return

            song_url = info['entries'][0]['webpage_url']
            info = await self.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
            # Now I could just do: return await self.cmd_play(player, channel, author, song_url)
            # But this is probably fine

        # TODO: Possibly add another check here to see about things like the bandcamp issue
        # TODO: Where ytdl gets the generic extractor version with no processing, but finds two different urls

        if 'entries' in info:
            # I have to do exe extra checks anyways because you can request an arbitrary number of search results
            if not permissions.allow_playlists and ':search' in info['extractor'] and len(info['entries']) > 1:
                raise exceptions.PermissionsError("You are not allowed to request playlists", expire_in=30)

            # The only reason we would use this over `len(info['entries'])` is if we add `if _` to this one
            num_songs = sum(1 for _ in info['entries'])

            if permissions.max_playlist_length and num_songs > permissions.max_playlist_length:
                raise exceptions.PermissionsError(
                    "Playlist has too many entries (%s > %s)" % (num_songs, permissions.max_playlist_length),
                    expire_in=30
                )

            # This is a little bit weird when it says (x + 0 > y), I might add the other check back in
            if permissions.max_songs and player.playlist.count_for_user(author) + num_songs > permissions.max_songs:
                raise exceptions.PermissionsError(
                    "Playlist entries + your already queued songs reached limit (%s + %s > %s)" % (
                        num_songs, player.playlist.count_for_user(author), permissions.max_songs),
                    expire_in=30
                )

            if info['extractor'].lower() in ['youtube:playlist', 'soundcloud:set', 'bandcamp:album']:
                try:
                    return await self._cmd_play_playlist_async(player, channel, author, permissions, song_url, info['extractor'])
                except exceptions.CommandError:
                    raise
                except Exception as e:
                    traceback.print_exc()
                    raise exceptions.CommandError("Error queuing playlist:\n%s" % e, expire_in=30)

            t0 = time.time()

            # My test was 1.2 seconds per song, but we maybe should fudge it a bit, unless we can
            # monitor it and edit the message with the estimated time, but that's some ADVANCED SHIT
            # I don't think we can hook into it anyways, so this will have to do.
            # It would probably be a thread to check a few playlists and get the speed from that
            # Different playlists might download at different speeds though
            wait_per_song = 1.2

            procmesg = await self.safe_send_message(
                channel,
                'Gathering playlist information for {} songs{}'.format(
                    num_songs,
                    ', ETA: {} seconds'.format(self._fixg(
                        num_songs * wait_per_song)) if num_songs >= 10 else '.'))

            # We don't have a pretty way of doing this yet.  We need either a loop
            # that sends these every 10 seconds or a nice context manager.
            await self.send_typing(channel)

            # TODO: I can create an event emitter object instead, add event functions, and every playlist might be asyncified
            #       Also have a "verify_entry" hook with the entry as an arg and returns the entry if its ok

            entry_list, position = await player.playlist.import_from(song_url, channel=channel, author=author)

            tnow = time.time()
            ttime = tnow - t0
            listlen = len(entry_list)
            drop_count = 0

            if permissions.max_song_length:
                for e in entry_list.copy():
                    if e.duration > permissions.max_song_length:
                        player.playlist.entries.remove(e)
                        entry_list.remove(e)
                        drop_count += 1
                        # Im pretty sure there's no situation where this would ever break
                        # Unless the first entry starts being played, which would make this a race condition
                if drop_count:
                    print("Dropped %s songs" % drop_count)

            print("Processed {} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
                listlen,
                self._fixg(ttime),
                ttime / listlen,
                ttime / listlen - wait_per_song,
                self._fixg(wait_per_song * num_songs))
            )

            await self.safe_delete_message(procmesg)

            if not listlen - drop_count:
                raise exceptions.CommandError(
                    "No songs were added, all songs were over max duration (%ss)" % permissions.max_song_length,
                    expire_in=30
                )

            reply_text = "Enqueued **%s** songs to be played. Position in queue: %s"
            btext = str(listlen - drop_count)

        else:
            if permissions.max_song_length and info.get('duration', 0) > permissions.max_song_length:
                raise exceptions.PermissionsError(
                    "Song duration exceeds limit (%s > %s)" % (info['duration'], permissions.max_song_length),
                    expire_in=30
                )

            try:
                entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)

            except exceptions.WrongEntryTypeError as e:
                if e.use_url == song_url:
                    print("[Warning] Determined incorrect entry type, but suggested url is the same.  Help.")

                if self.config.debug_mode:
                    print("[Info] Assumed url \"%s\" was a single entry, was actually a playlist" % song_url)
                    print("[Info] Using \"%s\" instead" % e.use_url)

                return await self.cmd_play(player, channel, author, permissions, leftover_args, e.use_url)

            reply_text = "Enqueued **%s** to be played. Position in queue: %s"
            btext = entry.title

            try:
                self.add_to_autoplaylist(entry.title, song_url, author.id)
            except:
                print("Failed to add song to apl in play command")

        if position == 1 and player.is_stopped:
            position = 'Up next!'
            reply_text %= (btext, position)

        else:
            try:
                time_until = await player.playlist.estimate_time_until(position, player)
                reply_text += ' - estimated time until playing: %s'
            except:
                traceback.print_exc()
                time_until = ''

            reply_text %= (btext, position, time_until)

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
                traceback.print_exc()
                raise exceptions.CommandError('Error handling playlist %s queuing.' % playlist_url, expire_in=30)

        elif extractor_type.lower() in ['soundcloud:set', 'bandcamp:album']:
            try:
                entries_added = await player.playlist.async_process_sc_bc_playlist(
                    playlist_url, channel=channel, author=author)
                # TODO: Add hook to be called after each song
                # TODO: Add permissions

            except Exception:
                traceback.print_exc()
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
                print("Dropped %s songs" % drop_count)

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
        print("Processed {}/{} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
            songs_processed,
            num_songs,
            self._fixg(ttime),
            ttime / num_songs,
            ttime / num_songs - wait_per_song,
            self._fixg(wait_per_song * num_songs))
        )

        if not songs_added:
            basetext = "No songs were added, all songs were over max duration (%ss)" % permissions.max_song_length
            if skipped:
                basetext += "\nAdditionally, the current song was skipped for being too long."

            raise exceptions.CommandError(basetext, expire_in=30)

        return Response("Enqueued {} songs to be played in {} seconds".format(
            songs_added, self._fixg(ttime, 1)), delete_after=30)

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

        return Response("Oh well :frowning:", delete_after=30)

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

            song_progress = str(timedelta(seconds=player.progress)).lstrip('0').lstrip(':')
            song_total = str(timedelta(seconds=player.current_entry.duration)).lstrip('0').lstrip(':')
            prog_str = '`[%s/%s]`' % (song_progress, song_total)
            np_text = ""

            if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
                np_text = "Now Playing: **%s** added by **%s** %s\n" % (
                    player.current_entry.title, player.current_entry.meta['author'].name, prog_str)


            #else:
            #    # AutoPlayList playing

            likers = ""
            for each_user in self.get_likers(player.current_entry.url):
                # strip off the unique identifiers
                # I'm not using the meta data since technically it has no author so I wrote a get_likers function
                if each_user == self._get_user(self.cur_author):
                    likers = likers + "**" + str(each_user)[:-5] + "**" + ", "
                else:
                    likers = likers + str(each_user)[:-5] + ", "

            # slice off last " ,""
            likers = likers[:-2]

            #Getting all tags for song
            list_tags = list(filter(lambda tag: player.current_entry.url in self.metaData[tag], self.metaData.keys()))
            if len(list_tags) != 0:
                the_tags = "\nTags: "
                for each_tag in list_tags:
                    the_tags += "**[" + each_tag + "]**, "
                the_tags = the_tags[:-2]
            else:
                the_tags = ""

            if np_text is not "":
                np_text += "\nLiked by: %s%s" % (likers, the_tags)
            else:
                np_text += "Now Playing: **%s** from the AutoPlayList. %s\nLiked by: %s%s" % (player.current_entry.title, prog_str, likers, the_tags)

            #self.server_specific_data[server]['last_np_msg'] = await self.safe_send_message(channel, np_text)
            #await self._manual_delete_check(message)
            return Response(
                np_text,
                delete_after=30
            )
        else:
            return Response(
                'There are no songs queued! Queue something with {}play.'.format(self.config.command_prefix),
                delete_after=30
            )

    async def cmd_summon(self, channel, author, voice_channel):
        """
        Usage:
            {command_prefix}summon

        Call the bot to the summoner's voice channel.
        """

        if not author.voice_channel:
            raise exceptions.CommandError('You are not in a voice channel!')

        voice_client = self.the_voice_clients.get(channel.server.id, None)
        if voice_client and voice_client.channel.server == author.voice_channel.server:
            await self.move_voice_client(author.voice_channel)
            return

        # move to _verify_vc_perms?
        chperms = author.voice_channel.permissions_for(author.voice_channel.server.me)

        if not chperms.connect:
            self.safe_print("Cannot join channel \"%s\", no permission." % author.voice_channel.name)
            return Response(
                "```Cannot join channel \"%s\", no permission.```" % author.voice_channel.name,
                delete_after=25
            )

        elif not chperms.speak:
            self.safe_print("Will not join channel \"%s\", no permission to speak." % author.voice_channel.name)
            return Response(
                "```Will not join channel \"%s\", no permission to speak.```" % author.voice_channel.name,
                delete_after=25
            )

        player = await self.get_player(author.voice_channel, create=True)

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

        cards = [':spades:',':clubs:',':hearts:',':diamonds:']
        hand = await self.send_message(channel, ' '.join(cards))
        await asyncio.sleep(0.6)

        for x in range(4):
            random.shuffle(cards)
            await self.safe_edit_message(hand, ' '.join(cards))
            await asyncio.sleep(0.6)

        await self.safe_delete_message(hand, quiet=True)
        return Response(":ok_hand:", delete_after=15)

    async def cmd_clear(self, player, author):
        """
        Usage:
            {command_prefix}clear

        Clears the playlist.
        """

        player.playlist.clear()
        return Response(':put_litter_in_its_place:', delete_after=20)

    async def cmd_skip(self, player, channel, author, message, permissions, voice_channel):
        """
        Usage:
            {command_prefix}skip

        Skips the current song when enough votes are cast, or by the bot owner.
        """

        if player.is_stopped:
            raise exceptions.CommandError("Can't skip! The player is not playing!", expire_in=20)

        if not player.current_entry:
            if player.playlist.peek():
                if player.playlist.peek()._is_downloading:
                    # print(player.playlist.peek()._waiting_futures[0].__dict__)
                    return Response("The next song (%s) is downloading, please wait." % player.playlist.peek().title)

                elif player.playlist.peek().is_downloaded:
                    print("The next song will be played shortly.  Please wait.")
                else:
                    print("Something odd is happening.  "
                          "You might want to restart the bot if it doesn't start working.")
            else:
                print("Something strange is happening.  "
                      "You might want to restart the bot if it doesn't start working.")

        if author.id == self.config.owner_id \
                or permissions.instaskip \
                or author == player.current_entry.meta.get('author', None) \
                or author in self.get_likers(player.current_entry.url) \
                or any(list(filter(lambda userID: userID in self.get_likers(player.current_entry.url), self.get_ghost_exist(author.id)))) \
                or player.current_entry.disliked == True:

            player.skip()  # check autopause stuff here
            await self._manual_delete_check(message)
            return

        # TODO: ignore person if they're deaf or take them out of the list or something?
        # Currently is recounted if they vote, deafen, then vote

        num_voice = sum(1 for m in voice_channel.voice_members if not (
            m.deaf or m.self_deaf or m.id in [self.config.owner_id, self.user.id]))

        num_skips = player.skip_state.add_skipper(author.id, message)

        skips_remaining = min(self.config.skips_required,
                              sane_round_int(num_voice * self.config.skip_ratio_required)) - num_skips

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

        if relative:
            vol_change = new_volume
            new_volume += (player.volume * 100)

        old_volume = int(player.volume * 100)

        if 0 < new_volume <= 100:

            player.volume = new_volume / 100.0
            if player.currently_playing:
                player.currently_playing.setVolume(player.volume)

            return Response('updated volume from %d to %d' % (old_volume, new_volume), reply=True, delete_after=20)

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
            song_progress = str(timedelta(seconds=player.progress)).lstrip('0').lstrip(':')
            song_total = str(timedelta(seconds=player.current_entry.duration)).lstrip('0').lstrip(':')
            prog_str = '`[%s/%s]`' % (song_progress, song_total)

            if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
                lines.append("Now Playing: **%s** added by **%s** %s\n" % (
                    player.current_entry.title, player.current_entry.meta['author'].name, prog_str))
            else:
                lines.append("Now Playing: **%s** %s\n" % (player.current_entry.title, prog_str))

        for i, item in enumerate(player.playlist, 1):
            if item.meta.get('channel', False) and item.meta.get('author', False):
                nextline = '`{}.` **{}** added by **{}**'.format(i, item.title, item.meta['author'].name).strip()
            else:
                nextline = '`{}.` **{}**'.format(i, item.title).strip()

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

        return Response('Cleaned up {} message{}.'.format(deleted, 's' * bool(deleted)), delete_after=15)

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

        return Response(":mailbox_with_mail:", delete_after=20)

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

        return Response(":mailbox_with_mail:", delete_after=20)


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
        return Response(":mailbox_with_mail:", delete_after=20)

    async def cmd_patchnotes(self, leftover_args):
        """
        Usage:
            {command_prefix}patchnotes

        Displays the most recent commit message on the repository
        """
        file = load_file(self.config.last_commit_file)
        textblock = ""
        for each_line in file:
            textblock += each_line;

        return Response("```\n" + textblock + "\n```", delete_after=30)


    async def cmd_playnow(self, player, channel, author, permissions, leftover_args, song_url):
        """
        Usage:
            {command_prefix}playnow song_link
            {command_prefix}playnow text to search for
        Stops the currently playing song and immediately plays the song requested. \
        If a link is not provided, the first result from a youtube search is played.
        """

        song_url = song_url.strip('<>')

        if permissions.max_songs and player.playlist.count_for_user(author) >= permissions.max_songs:
            raise exceptions.PermissionsError(
                "You have reached your enqueued song limit (%s)" % permissions.max_songs, expire_in=30
            )

        await self.send_typing(channel)

        if leftover_args:
            song_url = ' '.join([song_url, *leftover_args])

        # let's see if we already have this song or a similar one. i feel like this will help 70% of the time
        # let's check the songs the user likes before looking at other people's

        temp_url = await self.check_songs(song_url, author)
        if temp_url != None:
            song_url = temp_url

        try:
            info = await self.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
        except Exception as e:
            raise exceptions.CommandError(e, expire_in=30)

        if not info:
            raise exceptions.CommandError("That video cannot be played.", expire_in=30)

        # abstract the search handling away from the user
        # our ytdl options allow us to use search strings as input urls
        if info.get('url', '').startswith('ytsearch'):
            # print("[Command:play] Searching for \"%s\"" % song_url)
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
                return

            song_url = info['entries'][0]['webpage_url']
            info = await self.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
            # Now I could just do: return await self.cmd_play(player, channel, author, song_url)
            # But this is probably fine

        # TODO: Possibly add another check here to see about things like the bandcamp issue
        # TODO: Where ytdl gets the generic extractor version with no processing, but finds two different urls

        if 'entries' in info:
            raise exceptions.CommandError("Cannot playnow playlists! You must specify a single song.", expire_in=30)
        else:
            if permissions.max_song_length and info.get('duration', 0) > permissions.max_song_length:
                raise exceptions.PermissionsError(
                    "Song duration exceeds limit (%s > %s)" % (info['duration'], permissions.max_song_length),
                    expire_in=30
                )

            try:
                entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)
                await self.safe_send_message(channel, "Enqueued **%s** to be played. Position in queue: Up next!" % entry.title, expire_in=20)
                # Get the song ready now, otherwise race condition where finished-playing will fire before
                # the song is finished downloading, which will then cause another song from autoplaylist to
                # be added to the queue
                await entry.get_ready_future()

            except exceptions.WrongEntryTypeError as e:
                if e.use_url == song_url:
                    print("[Warning] Determined incorrect entry type, but suggested url is the same.  Help.")

                if self.config.debug_mode:
                    print("[Info] Assumed url \"%s\" was a single entry, was actually a playlist" % song_url)
                    print("[Info] Using \"%s\" instead" % e.use_url)

                return await self.cmd_playnow(player, channel, author, permissions, leftover_args, e.use_url)

            if position > 1:
                player.playlist.promote_last()
            if player.is_playing:
                player.skip()

            try:
                self.add_to_autoplaylist(entry.title, song_url, author.id)
            except:
                print("Failed to add song in playnow command")

        # return Response(reply_text, delete_after=30)

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
        except Exception as e:
            raise exceptions.CommandError(e, expire_in=20)

        return Response(":ok_hand:", delete_after=20)

    @owner_only
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

        return Response(":ok_hand:", delete_after=20)

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
            raise exceptions.CommandError("Unable to change avatar: %s" % e, expire_in=20)

        return Response(":ok_hand:", delete_after=20)


    async def cmd_disconnect(self, server):
        await self.disconnect_voice_client(server)
        return Response(":hear_no_evil:", delete_after=20)

    async def cmd_restart(self, channel):
        await self.safe_send_message(channel, ":wave:")
        await self.disconnect_all_voice_clients()
        raise exceptions.RestartSignal

    async def cmd_shutdown(self, channel):
        await self.safe_send_message(channel, ":wave:")
        await self.disconnect_all_voice_clients()
        raise exceptions.TerminateSignal

    async def cmd_execute(self, server, channel, author, message):

        lines = message.content
        print("COMMAND ===" + lines)
        lines = lines.split("\n")

        for each_line in lines:
            if "```" not in each_line or "execute" not in each_line:
                new_message = discord.Message(server=server, channel=channel, author=author, content=each_line)
                await self.on_message(each_line)
        return

    async def on_message(self, message):
        await self.wait_until_ready()

        message_content = message.content.strip()
        if not message_content.startswith(self.config.command_prefix):
            return

        if message.author == self.user:
            self.safe_print("Ignoring command from myself (%s)" % message.content)
            return

        if self.config.bound_channels and message.channel.id not in self.config.bound_channels and not message.channel.is_private:
            return  # if I want to log this I just move it under the prefix check


        if (is_latest_pickle(self.config.auto_playlist_pickle, self.last_modified_ts_apl) == False):
            self.autoplaylist = load_pickle(self.config.auto_playlist_pickle)
        if (is_latest_pickle(self.config.users_list_pickle, self.last_modified_ts_users) == False):
            self.users_list = load_pickle(self.config.users_list_pickle)

        command, *args = message_content.split()  # Uh, doesn't this break prefixes with spaces in them (it doesn't, config parser already breaks them)
        command = command[len(self.config.command_prefix):].lower().strip()

        handler = getattr(self, 'cmd_%s' % command, None)
        if not handler:
            return

        if message.channel.is_private:
            if not (message.author.id == self.config.owner_id and command == 'joinserver'):
                await self.send_message(message.channel, 'You cannot use this bot in private messages.')
                return

        if message.author.id in self.blacklist and message.author.id != self.config.owner_id:
            self.safe_print("[User blacklisted] {0.id}/{0.name} ({1})".format(message.author, message_content))
            return

        else:
            self.safe_print("[Command] {0.id}/{0.name} ({1})".format(message.author, message_content))

        user_permissions = self.permissions.for_user(message.author)

        argspec = inspect.signature(handler)
        params = argspec.parameters.copy()

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
                doc_key = '[%s=%s]' % (key, param.default) if param.default is not inspect.Parameter.empty else key
                args_expected.append(doc_key)

                if not args and param.default is not inspect.Parameter.empty:
                    params.pop(key)
                    continue

                if args:
                    arg_value = args.pop(0)
                    handler_kwargs[key] = arg_value
                    params.pop(key)

            if message.author.id != self.config.owner_id:
                if user_permissions.command_whitelist and command not in user_permissions.command_whitelist:
                    raise exceptions.PermissionsError(
                        "This command is not enabled for your group (%s)." % user_permissions.name,
                        expire_in=20)

                elif user_permissions.command_blacklist and command in user_permissions.command_blacklist:
                    raise exceptions.PermissionsError(
                        "This command is disabled for your group (%s)." % user_permissions.name,
                        expire_in=20)

            if params:
                docs = getattr(handler, '__doc__', None)
                if not docs:
                    docs = 'Usage: {}{} {}'.format(
                        self.config.command_prefix,
                        command,
                        ' '.join(args_expected)
                    )

                docs = '\n'.join(l.strip() for l in docs.split('\n'))
                await self.safe_send_message(
                    message.channel,
                    '```\n%s\n```' % docs.format(command_prefix=self.config.command_prefix),
                    expire_in=60
                )
                return

            response = await handler(**handler_kwargs)
            if response and isinstance(response, Response):
                content = response.content
                if response.reply:
                    content = '%s, %s' % (message.author.mention, content)

                sentmsg = await self.safe_send_message(
                    message.channel, content,
                    expire_in=response.delete_after if self.config.delete_messages else 0,
                    also_delete=message if self.config.delete_invoking else None
                )

            if (is_latest_pickle(self.config.auto_playlist_pickle, self.last_modified_ts_apl) == False):
                self.last_modified_ts_apl = store_pickle(self.config.auto_playlist_pickle, self.autoplaylist)
            if (is_latest_pickle(self.config.users_list_pickle, self.last_modified_ts_users) == False):
                self.last_modified_ts_users = store_pickle(self.config.users_list_pickle, self.users_list)

        except (exceptions.CommandError, exceptions.HelpfulError, exceptions.ExtractionError) as e:
            print("{0.__class__}: {0.message}".format(e))

            expirein = e.expire_in if self.config.delete_messages else None
            alsodelete = message if self.config.delete_invoking else None

            await self.safe_send_message(
                message.channel,
                '```\n%s\n```' % e.message,
                expire_in=expirein,
                also_delete=alsodelete
            )

        except exceptions.Signal:
            raise

        except Exception:
            traceback.print_exc()
            if self.config.debug_mode:
                await self.safe_send_message(message.channel, '```\n%s\n```' % traceback.format_exc())


    async def on_voice_state_update(self, before, after):
        if not all([before, after]):
            return

        if before.voice_channel == after.voice_channel:
            return

        if before.server.id not in self.players:
            return

        my_voice_channel = after.server.me.voice_channel  # This should always work, right?

        if not my_voice_channel:
            return

        if before.voice_channel == my_voice_channel:
            joining = False
        elif after.voice_channel == my_voice_channel:
            joining = True
        else:
            return  # Not my channel

        moving = before == before.server.me

        auto_paused = self.server_specific_data[after.server]['auto_paused']
        player = await self.get_player(my_voice_channel)

        if after == after.server.me and after.voice_channel:
            player.voice_client.channel = after.voice_channel

        if not self.config.auto_pause:
            return

        if sum(1 for m in my_voice_channel.voice_members if m != after.server.me):
            if auto_paused and player.is_paused:
                print("[config:autopause] Unpausing")
                self.server_specific_data[after.server]['auto_paused'] = False
                player.resume()
        else:
            if not auto_paused and player.is_playing:
                print("[config:autopause] Pausing")
                self.server_specific_data[after.server]['auto_paused'] = True
                player.pause()

    async def on_server_update(self, before:discord.Server, after:discord.Server):
        if before.region != after.region:
            self.safe_print("[Servers] \"%s\" changed regions: %s -> %s" % (after.name, before.region, after.region))

            await self.reconnect_voice_client(after)


if __name__ == '__main__':
    bot = MusicBot()
    bot.run()
