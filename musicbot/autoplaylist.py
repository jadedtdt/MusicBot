import logging

from .config import Config, ConfigDefaults
from .email import Email
from .song import Music
from .user import User
from .utils import load_file, write_file, get_latest_pickle_mtime, load_pickle, store_pickle, null_check_string
from .yti import YouTubeIntegration
log = logging.getLogger(__name__)

# note the scheme:
# add_* and remove_* refers to our dictionary of all users with Key: user_id, Value: list of Music objects
# _add_* and _remove_* refers to our list of python Users
# __add_* and __remove_* refers to our YTI (YouTubeIntegration)
class AutoPlaylist:

    def __init__(self, url_song_dict=None, users_list=None):

        self.yti = YouTubeIntegration()
        self.email_util = Email()

        config_file = ConfigDefaults.options_file
        self.config = Config(config_file)

        if url_song_dict:
            self._url_to_song_ = url_song_dict
        else:
            self._url_to_song_ = load_pickle(self.config.auto_playlist_pickle)

        self.last_modified_ts_apl = get_latest_pickle_mtime(self.config.auto_playlist_pickle)
        self.songs = list(self._url_to_song_.values())
        self.urls = list(self._url_to_song_.keys())

        if users_list:
            self.users_list = users_list
        else:
            self.users_list = load_pickle(self.config.users_list_pickle)

        self.last_modified_ts_users = get_latest_pickle_mtime(self.config.users_list_pickle)

    # adds to the master dictionary
    async def add_to_autoplaylist(self, url, title=None, author=None):

        url = self.check_url(url)

        if type(url) != str:
            log.error("[ADD_TO_AUTOPLAYLIST] URL was not a string: " + str(url))


        if author == None:
            log.warning("[ADD_TO_AUTOPLAYLIST] No Author... Don't know who to add to")
            return False

        if not self.get_user(author)[1]:
            new_user = self._get_user(author)
            log.error("[ADD_TO_AUTOPLAYLIST] Alert: Creating User profile for " + utils.null_check_string(new_user, 'name'))
            if self.new_autoplaylist.needs_reloaded():
                self._url_to_song_, self.users_list = self.new_autoplaylist.reload()         
            self.users_list.append(User(new_user.id, new_user.name))
            self.new_autoplaylist.store()

        if not author.isnumeric():
            author = author.id

        song = self.find_song_by_url(url)

        # if not on anyone's list, let's add it to someone's
        if song == None:
            log.debug("[ADD_TO_AUTOPLAYLIST] Creating new song object " + (title if title else "NO_TITLE"))
            song = Music(url, title, author)
            try:
                if await self._add_to_autoplaylist(url, title, author):
                    self._url_to_song_[url] = song
                    self.store()
                    return True
            except:
                log.error("[ADD_TO_AUTOPLAYLIST] Tried to add something that wasn't a url: " + str(url))
                return False
        # otherwise we just want to add this liker to the list
        else:
            if song.has_liker(author):
                log.debug("[ADD_TO_AUTOPLAYLIST] Song already added " + url)
                return False
            else:
                if await self._add_to_autoplaylist(url, title, author):
                    # appends current author to the end of the likers list
                    log.debug("[ADD_TO_AUTOPLAYLIST] Adding liker to song " + url)
                    song.add_liker(author)
                    return True

                if not self._url_to_song_[url].has_liker(author):
                    log.error("[ADD_TO_AUTOPLAYLIST] Failed to add liker to song " + url)
        return False

    # adds to the user's list
    async def _add_to_autoplaylist(self, url, title=None, author=None):

        url = self.check_url(url)

        if author == None:
            song = self.find_song_by_url(url)
            if song == None:
                log.debug("[_ADD_TO_AUTOPLAYLIST] Tried to add a song that's not in our APL yet")
                return self.add_to_autoplaylist(url, title, author)

            # trying to grab the likers from the apl
            likers = song.likers
            if likers == None:
                raise ValueError("No author and no likers. Can't add this song!")
            else:
                log.warning("[_ADD_TO_AUTOPLAYLIST] No author but we have list of likers, trying again!")
                for liker in likers:
                    success = await self._add_autoplaylist(url, title, liker)
                    if success == False:
                        return False
                return True

        user = self.get_user(author)[1]

        # if a user doesn't exist, we add them
        if user == None:
            raise NameError("User doesn't exist")

        # add a new url to users list of liked songs
        if url == None:
            raise ValueError("No valid URL given, cannot add.")

        if user.add_song(url):
            try:
                await self.__add_to_autoplaylist(url, title, author)
                return True
            except Exception as e:
                self.email_util.send_exception(user_id, title, "[_REMOVE_FROM_AUTOPLAYLIST] Failed to execute __remove_from_autoplaylist " + str(e))


        return False

    # adds to the user's YTI playlist
    async def __add_to_autoplaylist(self, url, title=None, author=None):

        if type(url) == Music:
            url = url.get_url()
            log.error("[__ADD_TO_AUTOPLAYLIST] URL {} passed is a Music obj, extracting URL".format(url))

        if author:
            musicbot_user = self.get_user(author)[1]
            if musicbot_user:
                if url:
                    url = self.check_url(url)

                    if musicbot_user.user_id:
                        playlist_id = self.yti.lookup_playlist(musicbot_user.user_id)
                        if playlist_id == None:
                            if musicbot_user.user_name:
                                log.debug("[__ADD_TO_AUTOPLAYLIST] Creating playlist for user: {}".format(musicbot_user.user_name))
                                self.yti.create_playlist(musicbot_user.user_name.replace(' ', '-'), musicbot_user.user_id)
                                #have to wait for our api request to take effect
                                time.sleep(2)
                            else:
                                log.error("[__ADD_TO_AUTOPLAYLIST] Name was null. ID: {}".format(musicbot_user.user_id))

                        if "youtube" in url or "youtu.be" in url:
                            video_id = self.yti.extract_youtube_video_id(url)
                            if video_id:
                                video_playlist_id = self.yti.lookup_video(video_id, playlist_id)
                                if video_playlist_id == None:
                                    try:
                                        self.yti.add_video(musicbot_user.user_id, video_id)
                                        return True
                                    except Exception as e:
                                        log.error("[__ADD_TO_AUTOPLAYLIST] Failed to add video {} for User: {}".format(title if title else url, musicbot_user.user_id))
                                        self.email_util.send_exception(musicbot_user.user_id, None, "[__REMOVE_FROM_AUTOPLAYLIST] " + str(e))
                                else:
                                    log.debug("Song {} already added to YTI Playlist {}".format(title, musicbot_user.user_name))
                            else:
                                log.error("[__ADD_TO_AUTOPLAYLIST] video_id is None for url {}".format(url))
                        else:
                            log.warning("[__ADD_TO_AUTOPLAYLIST] Not a youtube URL: {}".format(url))
                    else:
                        log.error("[__ADD_TO_AUTOPLAYLIST] user_id was null. Author: {}".format(musicbot_user.user_name))
                else:
                    log.error("[__ADD_TO_AUTOPLAYLIST] url was null. Author: {}".format(musicbot_user.user_name))
            else:
                log.error("[__ADD_TO_AUTOPLAYLIST] musicbot_user was null.")
        else:
            log.error("[__ADD_TO_AUTOPLAYLIST] author was null")
        return False

    # removes the master dictionary
    async def remove_from_autoplaylist(self, url, title=None, author=None):

        url = self.check_url(url)

        if author:

            if not str(author).isnumeric():
                author = author.id
            user = self.get_user(author)[1]

            song = self.find_song_by_url(url)

            if song:

                if not song.has_liker(author):
                    log.debug("[REMOVE_FROM_AUTOPLAYLIST] Hey! You can't remove a song that's not even yours!")
                    return False

                if len(song.likers) > 1:
                    log.debug("[REMOVE_FROM_AUTOPLAYLIST] MULTIPLE LIKERS, REMOVING: " + null_check_string(song, 'title'))
                    if await self._remove_from_autoplaylist(url, title, author):
                        if song.remove_liker(author):
                            self.store()
                            return True
                    else:
                        return False
                
                elif len(song.likers) == 1:
                    log.debug("[REMOVE_FROM_AUTOPLAYLIST] ONE LIKER, REMOVING: " + null_check_string(song, 'title'))

                    #removing the song from the metadata dict (tags)
                    try:
                        if song.url in list(self.metaData.values()):
                            for each_key in list(self.metaData.keys()):
                                if song.url in self.metaData[each_key]:
                                    self.metaData[each_key].remove(song.url)
                    except:
                        pass

                    #removing the song from the APL for GOOD
                    try:
                        if await self._remove_from_autoplaylist(url, title, author):
                            self._url_to_song_.pop(url)
                            self.store()
                            return True
                        else:
                            return False
                    except:
                        log.error("[REMOVE_FROM_AUTOPLAYLIST] Tried to remove something that wasn't a url: " + str(url))
                        return False
                else:
                    log.warning("[REMOVE_FROM_AUTOPLAYLIST] NO LIKERS, NOT REMOVING: " + null_check_string(song, 'title'))
                    return False


            else:
                log.warning("[REMOVE_FROM_AUTOPLAYLIST] Can't remove a song that's not in the auto playlist")
                return False
        else:
            log.warning("REMOVE_FROM_AUTOPLAYLIST] No author")

    # removes from user's list of songs
    async def _remove_from_autoplaylist(self, url, title=None, author=None):

        user = self.get_user(author)[1]

        if user:
            url = self.check_url(url)

            if user.has_song(url):
                if user.remove_song(url):
                    log.debug("[_REMOVE_FROM_AUTOPLAYLIST] REMOVE SUCCESS!")
                    try:
                        await self.__remove_from_autoplaylist(url, title, author)
                        self.store()
                        return True
                    except Exception as e:
                        self.email_util.send_exception(user_id, title, "[_REMOVE_FROM_AUTOPLAYLIST] Failed to execute __remove_from_autoplaylist " + str(e))
                else:
                    log.debug("[_REMOVE_FROM_AUTOPLAYLIST] REMOVE FAILED!")
            else:
                log.warning("[_REMOVE_FROM_AUTOPLAYLIST] The song isn't in the user's personal list")

        return False

    # removes from user's YTI playlist
    async def __remove_from_autoplaylist(self, url, title=None, author=None):

        if type(url) == Music:
            url = url.get_url()
            log.error("[__REMOVE_FROM_AUTOPLAYLIST] URL {} passed is a Music obj, extracting URL".format(url))

        if author:
            musicbot_user = self.get_user(author)[1]
            if musicbot_user:
                if url:
                    url = self.check_url(url)

                    if musicbot_user.user_id:
                        playlist_id = self.yti.lookup_playlist(musicbot_user.user_id)
                        if playlist_id:
                            if "youtube" in url or "youtu.be" in url:
                                video_id = self.yti.extract_youtube_video_id(url)
                                if video_id:
                                    if self.yti.lookup_video(video_id, playlist_id):
                                        try:
                                            self.yti.remove_video(musicbot_user.user_id, video_id)
                                            return True
                                        except Exception as e:
                                            log.error("[__REMOVE_FROM_AUTOPLAYLIST] Failed to remove video {} for User: {}".format(title if title else url, musicbot_user.user_id))
                                            self.email_util.send_exception(musicbot_user.user_id, None, "[__REMOVE_FROM_AUTOPLAYLIST] " + str(e))
                                    else:
                                        log.error("[__REMOVE_FROM_AUTOPLAYLIST] Video {} is not in playlist {}".format(title, musicbot_user.user_name))
                                else:
                                    log.error("[__REMOVE_FROM_AUTOPLAYLIST] video_id is None for url {}".format(title))
                            else:
                                log.debug("[__REMOVE_FROM_AUTOPLAYLIST] Not a youtube URL: {}".format(url))
                        else:
                            log.warning("[__REMOVE_FROM_AUTOPLAYLIST] Playlist doesn't exist, can't delete from it. ID: {}".format(musicbot_user.user_id))
                    else:
                        log.error("[__REMOVE_FROM_AUTOPLAYLIST] user_id was null. Author: {}".format(musicbot_user.user_name))
                else:
                    log.error("[__REMOVE_FROM_AUTOPLAYLIST] url was null. Author: {}".format(musicbot_user.user_name))
            else:
                log.error("[__REMOVE_FROM_AUTOPLAYLIST] musicbot_user was null")
        else:
            log.error("[__REMOVE_FROM_AUTOPLAYLIST] author was null")
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

    def store(self):

        log.debug("[ON_PLAYER_FINISHED_PLAYING] Storing latest APL pickle file")
        store_pickle(self.config.auto_playlist_pickle, self._url_to_song_)
        self.last_modified_ts_apl = get_latest_pickle_mtime(self.config.auto_playlist_pickle)

        log.debug("[ON_PLAYER_FINISHED_PLAYING] Storing latest users pickle file")
        store_pickle(self.config.users_list_pickle, self.users_list)
        self.last_modified_ts_users = get_latest_pickle_mtime(self.config.users_list_pickle)

    def reload(self):

        log.debug("[ON_PLAYER_FINISHED_PLAYING] Loading latest APL pickle file")
        self._url_to_song_ = load_pickle(self.config.auto_playlist_pickle)
        self.songs = list(self._url_to_song_.values())
        self.urls = list(self._url_to_song_.keys())
        self.last_modified_ts_apl = get_latest_pickle_mtime(self.config.auto_playlist_pickle)

        log.debug("[ON_PLAYER_FINISHED_PLAYING] Loading latest users pickle file")
        self.users_list = load_pickle(self.config.users_list_pickle)
        self.last_modified_ts_users = get_latest_pickle_mtime(self.config.users_list_pickle)

        return self._url_to_song_, self.users_list

    def needs_reloaded(self):

        return get_latest_pickle_mtime(self.config.users_list_pickle) > self.last_modified_ts_users \
            or get_latest_pickle_mtime(self.config.users_list_pickle) > self.last_modified_ts_users

    def get_user(self, discord_user):

        discord_id = -1

        # forces us to have id
        if not str(discord_user).isnumeric():
            discord_id = discord_user.id
        else:
            discord_id = discord_user

        for i, each_user in enumerate(self.users_list):
            if each_user.user_id == discord_id:
                return i, each_user

        return 0, None
        
    def check_url(self, url):

        if url:
            if 'www.' in url and 'https://' not in url:
                url = 'https://' + url
            if '?t=' in url:
                url = url.split('?t=')[0]
            if '&t' in url or '&index' in url or '&list' in url:
                url = url.split('&')[0]
        return url
