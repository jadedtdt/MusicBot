import asyncio
import configparser
import logging
import MySQLdb

from datetime import datetime

from .config import Config, ConfigDefaults
from .email import Email
from .song import Music
from .sqlfactory import SqlFactory
from .user import User
from .utils import load_file, write_file, get_latest_pickle_mtime, load_pickle, store_pickle, null_check_string
from .yti import YouTubeIntegration
log = logging.getLogger(__name__)

# note the scheme:
# add_* and remove_* refers to our dictionary of all users with Key: user_id, Value: list of Music objects
# _add_* and _remove_* refers to our list of python Users
# __add_* and __remove_* refers to our YTI (YouTubeIntegration)
class AutoPlaylist:

    def __init__(self):

        self.yti = YouTubeIntegration()
        self.email_util = Email()

        config_file = ConfigDefaults.options_file
        self.config = Config(config_file)

        self._url_to_song_ = load_pickle(self.config.auto_playlist_pickle)
        self.last_modified_ts_apl = get_latest_pickle_mtime(self.config.auto_playlist_pickle)

        self.users_list = load_pickle(self.config.users_list_pickle)
        self.last_modified_ts_users = get_latest_pickle_mtime(self.config.users_list_pickle)

        self.songs = list(self._url_to_song_.values())
        self.urls = list(self._url_to_song_.keys())

    async def create_song(self, url, title=None, play_count=0, volume=0.15, updt_dt_tm='CURRENT_TIMESTAMP()', cret_dt_tm='CURRENT_TIMESTAMP()'):

        await self.sqlfactory.create_song(table, query, [url, title, play_count, volume, updt_dt_tm, cret_dt_tm])
        log.info('INSERTED A NEW SONG, WOW!')

    async def add_to_autoplaylist(self, url, title=None, author=None):

        if not url:
            log.error("[ADD_TO_AUTOPLAYLIST] No URL. Don't know what song to add.")
            return False

        if not author:
            log.error("[ADD_TO_AUTOPLAYLIST] No author. Don't know who to add to.")
            return False

        if not author.isnumeric():
            author = author.id

        url = self.check_url(url)

        # attempt the 3 process flow
        if self.needs_reloaded():
            self._url_to_song_, self.users_list = self.reload()

        dict_success = await self._add_to_song_dictionary(url, title, author)
        users_list_success = await self._add_to_users_list(url, title, author)

        if dict_success and users_list_success:

            # only do 3rd process for youtube links
            if "youtube" in url or "youtu.be" in url:
                await self._add_to_yti_add_file(url, title, author)

            self.store(self._url_to_song_, self.users_list)
            return True
        elif (not dict_success and users_list_success) or (dict_success and not users_list_success):
            self.email_util.send_exception(author, url, "[ADD_TO_AUTOPLAYLIST] CORRUPTION DETECTED! dict_success: {}, users_list: {}".format(dict_success, users_list))

        # rollback
        self._url_to_song_, self.users_list = self.reload()
        return False

    # adds to the master dictionary
    async def _add_to_song_dictionary(self, url, title=None, author=None):

        song = self.find_song_by_url(url)

        # if not on anyone's list, let's add it to someone's
        if not song:
            log.debug("[_ADD_TO_SONG_DICTIONARY] Creating new song object " + str(song))
            song = Music(url, title, author)
            try:
                self._url_to_song_[url] = song
                return True
            except:
                log.error("[_ADD_TO_SONG_DICTIONARY] Tried to add something that wasn't a url: " + str(url))
        # otherwise we just want to add this liker to the list
        else:
            if song.has_liker(author):
                log.debug("[_ADD_TO_SONG_DICTIONARY] Song already added " + url)
            else:
                log.debug("[_ADD_TO_SONG_DICTIONARY] Adding liker to song " + url)
                song.add_liker(author)
                return True

        return False

    # adds to the user's list
    async def _add_to_users_list(self, url, title=None, author=None):

        user = self.get_user(author)

        if user.add_song(url):
            return True
        else:
            log.error("[_ADD_TO_USERS_LIST] Failed to add URL {} to user's {} list ".format(url, str(user)))

        return False

    # adds url to serialized dictionary to add to users' YT playlists
    async def _add_to_yti_add_file(self, url, title=None, author=None):

        try:
            temp_pickle = load_pickle('../MusicBot/data/yti-add_{}.pickle'.format(datetime.today().strftime('%Y-%m-%d')))
            yti_add_pickle = temp_pickle
            yti_add_pickle.user_dict[author].append(url)
            store_pickle('../MusicBot/data/yti-add_{}.pickle'.format(datetime.today().strftime('%Y-%m-%d')), yti_add_pickle)
        except Exception as e:
            yti_add_pickle = {}
            yti_add_pickle[author] = [url]
            store_pickle('../MusicBot/data/yti-add_{}.pickle'.format(datetime.today().strftime('%Y-%m-%d')), yti_add_pickle)

    # deprecated :( this will be handled by a cron job
    # adds to the user's YTI playlist
    async def _add_to_yti_playlist(self, url, title=None, author=None):

        user = self.get_user(author)

        # temp reference for debugging
        song = Music(url, title, author)

        # should be preprocessed but im a scaredy cat
        if "youtube" not in url and "youtu.be" not in url:
            log.debug("[_ADD_TO_YTI_PLAYLIST] Not a youtube URL: {}".format(url))
            return True

        playlist_id = self.yti.lookup_playlist(author)

        if not playlist_id:
            log.debug("[_ADD_TO_YTI_PLAYLIST] Creating playlist for user: {}".format(str(user)))
            self.yti.create_playlist(self.null_check_string(user, 'user_name').replace(' ', '-'), user.user_id)
            # let's wait for our api request to take effect
            time.sleep(2)

        playlist_id = self.yti.lookup_playlist(author)

        try:
            video_id = self.yti.extract_youtube_video_id(url)
            video_playlist_id = self.yti.lookup_video(video_id, playlist_id)
            if not video_playlist_id:
                self.yti.add_video(user.user_id, video_id)
                return True
            else:
                log.debug("[_ADD_TO_YTI_PLAYLIST] Song {} was already added to YTI Playlist {}".format(str(song), str(user)))
        except Exception as e:
            log.error("[_ADD_TO_YTI_PLAYLIST] Failed to add video {} for user {}".format(str(song), user.user_id))
            self.email_util.send_exception(user.user_id, song, "[_ADD_TO_YTI_PLAYLIST] " + str(e))

        return False

    # removes the master dictionary
    async def remove_from_autoplaylist(self, url, title=None, author=None):

        if not url:
            log.error("[REMOVE_FROM_AUTOPLAYLIST] No URL. Don't know what song to add.")
            return False

        if not author:
            log.error("[REMOVE_FROM_AUTOPLAYLIST] No author. Don't know who to add to.")
            return False

        if not author.isnumeric():
            author = author.id

        url = self.check_url(url)

        # attempt the 3 process flow
        if self.needs_reloaded():
            self._url_to_song_, self.users_list = self.reload()

        dict_success = await self._remove_from_song_dictionary(url, title, author)
        users_list_success = await self._remove_from_users_list(url, title, author)

        if dict_success and users_list_success:

            # only do 3rd process for youtube links
            if "youtube" in url or "youtu.be" in url:
                await self._add_to_yti_remove_file(url, title, author)

            self.store(self._url_to_song_, self.users_list)
            return True
        elif (not dict_success and users_list_success) or (dict_success and not users_list_success):
            self.email_util.send_exception(author, url, "[REMOVE_FROM_AUTOPLAYLIST] CORRUPTION DETECTED! dict_success: {}, users_list: {}".format(dict_success, users_list_success))

        # rollback
        self._url_to_song_, self.users_list = self.reload()
        return False

    # removes the master dictionary
    async def _remove_from_song_dictionary(self, url, title=None, author=None):

            song = self.find_song_by_url(url)

            # we can only remove songs that have been added to the dict
            if song and song.likers and (author in song.likers):
                # remove author from list of likers in song obj
                if len(song.likers) > 1:
                    log.debug("[_REMOVE_FROM_SONG_DICTIONARY] MULTIPLE LIKERS, REMOVING: " + str(song))
                    if song.remove_liker(author):
                        return True
                    else:
                        log.error("[_REMOVE_FROM_SONG_DICTIONARY] Failed to remove liker {} from song {} in dictionary: ".format(author, str(song)))

                # last liker left; deleting song object
                elif len(song.likers) == 1:
                    log.debug("[_REMOVE_FROM_SONG_DICTIONARY] ONE LIKER, REMOVING: " + str(song))

                    #TODO add metadata file to this file
                    #removing the song from the metadata dict (tags)
                    #try:
                    #    if song.url in list(self.metaData.values()):
                    #        for each_key in list(self.metaData.keys()):
                    #            if song.url in self.metaData[each_key]:
                    #                self.metaData[each_key].remove(song.url)
                    #except Exception as e:
                    #    self.email_util.send_exception(author, song, "[_REMOVE_FROM_SONG_DICTIONARY] Failed to remove song from meta data file. " + str(e))

                    #removing the song from the APL for GOOD
                    try:
                        self._url_to_song_.pop(url)
                        return True
                    except Exception as e:
                        log.error("[_REMOVE_FROM_SONG_DICTIONARY] Tried to remove something that wasn't a url: " + str(url))

                # no likers for this song object.. let's tell ourselves to clean up this mess
                else:
                    log.warning("[_REMOVE_FROM_SONG_DICTIONARY] NO LIKERS, NOT REMOVING: " + str(song))
                    self.email_util.send_exception(author, song, "[_REMOVE_FROM_SONG_DICTIONARY] Song had no likers. Remove it manually. " + str(e))

                return False
            else:
                log.warning("[_REMOVE_FROM_SONG_DICTIONARY] Can't remove a song that's not in the auto playlist")
                return False

    # removes from user's list of songs
    async def _remove_from_users_list(self, url, title=None, author=None):

        user = self.get_user(author)

        try:
            if user.remove_song(url):
                return True
        except Exception as e:
            log.warning("[_REMOVE_FROM_USERS_LIST] Failed to remove song {} from user's {} playlist".format(str(url), str(user)))

        return False

    # adds url to serialized dictionary to remove from users' YT playlists
    async def _add_to_yti_remove_file(self, url, title=None, author=None):

        try:
            temp_pickle = load_pickle('../MusicBot/data/yti-remove_{}.pickle'.format(datetime.today().strftime('%Y-%m-%d')))
            yti_remove_pickle = temp_pickle
            yti_remove_pickle.user_dict[author].append(url)
            store_pickle('../MusicBot/data/yti-remove_{}.pickle'.format(datetime.today().strftime('%Y-%m-%d')), yti_remove_pickle)
        except Exception as e:
            yti_remove_pickle = {}
            yti_remove_pickle[author] = [url]
            store_pickle('../MusicBot/data/yti-remove_{}.pickle'.format(datetime.today().strftime('%Y-%m-%d')), yti_remove_pickle)

    # deprecated :( this will be handled by a cron job
    # removes from user's YTI playlist
    async def _remove_from_yti_playlist(self, url, title=None, author=None):

        user = self.get_user(author)

        # should be preprocessed but im a scaredy cat
        if "youtube" not in url and "youtu.be" not in url:
            log.debug("[_REMOVE_FROM_YTI_PLAYLIST] Not a youtube URL: {}".format(url))
            return True

        try:
            playlist_id = self.yti.lookup_playlist(user.user_id)
            video_id = self.yti.extract_youtube_video_id(url)
            self.yti.remove_video(user.user_id, video_id)
            return True

        except Exception as e:
            log.error("[_REMOVE_FROM_YTI_PLAYLIST] Failed to remove video {} for User: {}".format(title if title else url, user.user_id))
            self.email_util.send_exception(user.user_id, None, "[_REMOVE_FROM_YTI_PLAYLIST] " + str(e))

        return False

    # finds the first instance a song URL is found or if a string is found in a title and returns the object
    def find_song_by_url(self, url):

        url = self.check_url(url)

        found_song = None

        try:
            found_song = self._url_to_song_[url]
        except:
            found_song = None

        return found_song

    def store(self, _url_to_song_, users_list):

        log.debug("[ON_PLAYER_FINISHED_PLAYING] Storing latest APL pickle file")
        store_pickle(self.config.auto_playlist_pickle, _url_to_song_)
        self.last_modified_ts_apl = get_latest_pickle_mtime(self.config.auto_playlist_pickle)

        log.debug("[ON_PLAYER_FINISHED_PLAYING] Storing latest users pickle file")
        store_pickle(self.config.users_list_pickle, users_list)
        self.last_modified_ts_users = get_latest_pickle_mtime(self.config.users_list_pickle)

    def reload(self):

        log.debug("[ON_PLAYER_FINISHED_PLAYING] Loading latest APL pickle file")
        self._url_to_song_ = load_pickle(self.config.auto_playlist_pickle)
        self.last_modified_ts_apl = get_latest_pickle_mtime(self.config.auto_playlist_pickle)

        log.debug("[ON_PLAYER_FINISHED_PLAYING] Loading latest users pickle file")
        self.users_list = load_pickle(self.config.users_list_pickle)
        self.last_modified_ts_users = get_latest_pickle_mtime(self.config.users_list_pickle)

        return self._url_to_song_, self.users_list

    def needs_reloaded(self):

        return get_latest_pickle_mtime(self.config.auto_playlist_pickle) > self.last_modified_ts_users \
            or get_latest_pickle_mtime(self.config.users_list_pickle) > self.last_modified_ts_users

    def get_user(self, discord_user):

        discord_id = -1

        # forces us to have id
        if not str(discord_user).isnumeric():
            discord_id = discord_user.id
        else:
            discord_id = discord_user

        for each_user in self.users_list:
            if each_user.user_id == discord_id:
                return each_user

        return None
        
    def check_url(self, url):

        if url:
            if 'www.' in url and 'https://' not in url:
                url = 'https://' + url
            if '?t=' in url:
                url = url.split('?t=')[0]
            if '&t' in url or '&index' in url or '&list' in url:
                url = url.split('&')[0]
        return url
