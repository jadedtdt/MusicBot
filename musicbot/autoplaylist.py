import asyncio
import configparser
import logging
import MySQLdb

from datetime import datetime

from .config import Config, ConfigDefaults
from .email import Email
from .song import Song
from .sqlfactory import SqlFactory
from .user import User
from .utils import load_file, write_file, null_check_string
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
        self._sqlfactory = SqlFactory()

        config_file = ConfigDefaults.options_file
        self.config = Config(config_file)

        self._songs = self._get_songs()
        self._users = self._get_users()

        self._NUM_COLS_USER = 6
        self._NUM_COLS_SONG = 6


    @property
    def songs(self):
        return self._songs

    @songs.setter
    def songs(self, new_songs):
        if new_songs:
            if type(new_songs) != list:
                new_songs = list(new_songs)
        else:
            raise ValueError("AutoPlaylist tried to use songs setter but argument was None")
        self._songs = new_songs

    @property
    def users(self):
        return self._users

    @users.setter
    def users(self, new_users):
        if new_users:
            if type(new_users) != list:
                new_users = list(new_users)
        else:
            raise ValueError("AutoPlaylist tried to use users setter but argument was None")
        self._users = new_users

    @property
    def sqlfactory(self):
        return self._sqlfactory

    async def user_like_song(self, user_id, url, title=None, play_count=0, volume=0.15, updt_dt_tm=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), cret_dt_tm=datetime.now().strftime('%Y-%m-%d %H:%M:%S')):

        # passed in User instead of id
        if type(user_id) == User:
            user_id = user_id.user_id
        # passed in int
        if type(user_id) == int:
            user_id = str(user_id)
        # passed in null URL
        if not url:
            log.warning("Null URL passed into user_like_song. Aborting")
            return False

        success_song, success_user_song = [False, False]

        if not await self._sqlfactory.song_read(url):
            success_song = await self._sqlfactory.song_create(url, title, play_count, volume, updt_dt_tm, cret_dt_tm)
            if not success_song:
                log.error("Failed to create song {} {}".format(url, title if title else "No Title"))
                self.email_util.send_exception(user_id, None, "[user_like_song] [song] Check for corruption " + url)
                log.error("Failed to create song {} {}".format(url, title if title else "No Title"))
                return False
            else:
                log.debug("Successfully created song {} {}".format(url, title if title else "No Title"))
        else:
            log.error("song is there??")

        if not await self._sqlfactory.user_song_read(user_id, url):
            success_user_song = await self._sqlfactory.user_song_create(user_id, url, play_count, cret_dt_tm)            
            if not success_user_song:
                log.error("Check corruption! {} {}".format(url, title if title else "No Title"))
                self.email_util.send_exception(user_id, None, "[user_like_song] [user_song] Check for corruption " + url)
                log.error("Failed to create user_song {} {}".format(url, title if title else "No Title"))
                return False
            else:
                log.debug("Successfully created user_song {} {}".format(url, title if title else "No Title"))

        return success_song==True and success_user_song==True

    async def user_dislike_song(self, user_id, url, title=None):

        # passed in User instead of id
        if type(user_id) == User:
            user_id = user_id.user_id
        # passed in int
        if type(user_id) == int:
            user_id = str(user_id)
        # passed in null URL
        if not url:
            log.warning("Null URL passed into user_like_song. Aborting")
            return False

        success_song, success_user_song = [False, False]

        if await self._sqlfactory.user_song_read(user_id, url):
            success_user_song = await self._sqlfactory.user_song_delete(user_id, url)
            if not success_user_song:
                log.error("Check corruption! {} {}".format(url, title if title else "No Title"))
                self.email_util.send_exception(user_id, None, "[user_dislike_song] [user_song] Check for corruption " + url)
                log.error("Failed to delete user_song {} {}".format(url, title if title else "No Title"))
                return False
            else:
                log.debug("Successfully deleted user_song {} {}".format(url, title if title else "No Title"))

                success_count, result_set = await self._sqlfactory.execute('SELECT COUNT(*) FROM USER_SONG WHERE URL = %s', [url])
                log.info('FAIL0: ' + str(result_set))
                count = result_set[0]
                if success_count and count[0] == '0' and success_user_song:
                    success_song = await self._sqlfactory.song_delete(url)
                    if not success_song:
                        log.error("Check corruption! {} {}".format(url, title if title else "No Title"))
                        self.email_util.send_exception(user_id, None, "[user_dislike_song] [song] Check for corruption " + url)
                        log.error("Failed to delete song {} {}".format(url, title if title else "No Title"))
                        return False
                    else:
                        log.debug("Successfully deleted song {} {}".format(url, title if title else "No Title"))
                else:
                    log.info('FAIL1: ' + str(success_count))
                    log.info('FAIL2: ' + str(count))
                    log.info('FAIL3: ' + str(success_user_song))

            return True
        else:
            log.warning('Song {}-{} doesnt exist in this users list {}'.format(url, title if title else 'No Title', user_id))

        return False

    async def are_songs_available(self):
        success_count, result_set = await self._sqlfactory.execute("SELECT COUNT(*) FROM SONG WHERE '1' = %s", ['1'])
        if success_count and result_set:
            return int(result_set[0]) > 0
        return str(result_set[0]) > '0'

    async def get_user(self, user_id):

        discord_id = -1

        # forces us to have id
        if not str(user_id).isnumeric():
            discord_id = user_id.id
        else:
            discord_id = user_id

        user_result = await self._sqlfactory.user_read(str(discord_id))
        if user_result and str(user_result[0]) == str(discord_id):
            return User(user_result[0], user_result[1], user_result[2], user_result[3])

        return None

    async def find_song_by_url(self, url):
        return self._find_song_by_url(url)

    def _find_song_by_url(self, url):
        song = None
        result_set = self._sqlfactory._song_read(url)
        if result_set:
            each_row = result_set[0]
            #log.debug('each_row ! ' + str(each_row))
            url, title, play_count, volume, updt_dt_tm, cret_dt_tm = each_row
            volume = str(volume)
            song = Song(url, title, play_count, volume, updt_dt_tm, cret_dt_tm)
        return song

    async def find_songs_by_title(self, title):
        return self._find_songs_by_title(title)

    def _find_songs_by_title(self, title):
        if not title:
            return None
        songs = []
        success_select, result_set = self._sqlfactory._execute('SELECT SONG.* FROM SONG WHERE SONG.TITLE LIKE %s', ['%{}%'.format(title)] )
        
        if success_select and result_set:
            for each_row in result_set:
                #log.debug('each_row ! ' + str(each_row))
                url, title, play_count, volume, updt_dt_tm, cret_dt_tm = each_row
                volume = str(volume)
                song = Song(url, title, play_count, volume, updt_dt_tm, cret_dt_tm)
                songs.append(song)
        return songs

    async def get_likers(self, url):
        return self._get_likers(url)

    def _get_likers(self, url):
        likers = []
        success_select, result_set = self._sqlfactory._execute('SELECT USER.* FROM USER INNER JOIN USER_SONG ON USER.ID = USER_SONG.ID WHERE USER_SONG.URL = %s', [url])
        if success_select and result_set:
            for each_row in result_set:
                #log.debug('each_row ! ' + str(each_row))
                user_id, user_name, mood, yti_url, updt_dt_tm, cret_dt_tm = each_row
                new_user = User(user_id, user_name, mood, yti_url, updt_dt_tm, cret_dt_tm)
                likers.append(new_user)
        return likers


    async def get_songs(self):
        return self._get_songs()

    def _get_songs(self):
        songs = []
        success_select, result_set = self._sqlfactory._execute('SELECT * FROM SONG WHERE 1 = %s', ['1'])
        if success_select and result_set:
            for each_row in result_set:
                #log.debug('each_row ! ' + str(each_row))
                url, title, play_count, volume, updt_dt_tm, cret_dt_tm = each_row
                volume = str(volume)
                new_song = Song(url, title, play_count, volume, updt_dt_tm, cret_dt_tm)
                songs.append(new_song)
        return songs

    async def get_users(self):
        return self._get_users()

    def _get_users(self):
        users = []
        success_select, result_set = self._sqlfactory._execute('SELECT * FROM USER WHERE 1 = %s', ['1'])
        if success_select and result_set:
            for each_row in result_set:
                #log.debug('each_row ! ' + str(each_row))
                user_id, user_name, mood, yti_url, updt_dt_tm, cret_dt_tm = each_row
                new_user = User(user_id, user_name, mood, yti_url)
                users.append(new_user)
        return users

    async def get_user_songs(self, user_id):
        return self._get_user_songs(user_id)

    def _get_user_songs(self, user_id):
        user_songs = []
        success_select, result_set = self._sqlfactory._execute('SELECT SONG.* FROM SONG INNER JOIN USER_SONG ON USER_SONG.URL = SONG.URL WHERE USER_SONG.ID = %s', [user_id])
        if success_select and result_set:
            for each_row in result_set:
                #log.debug('each_row ! ' + str(each_row))
                url, title, play_count, volume, updt_dt_tm, cret_dt_tm = each_row
                volume = str(volume)
                new_song = Song(url, title, play_count, volume, updt_dt_tm, cret_dt_tm)
                user_songs.append(new_song)
        return user_songs

    # deprecated :( this will be handled by a cron job
    # adds to the user's YTI playlist
    async def _add_to_yti_playlist(self, url, title=None, author=None):

        user = self.get_user(author)

        # temp reference for debugging
        song = Song(url, title, author)

        # should be preprocessed but im a scaredy cat
        if "youtube" not in url and "youtu.be" not in url:
            log.debug("[_ADD_TO_YTI_PLAYLIST] Not a youtube URL: {}".format(url))
            return True

        playlist_id = self.yti.lookup_playlist(author)

        if not playlist_id:
            log.debug("[_ADD_TO_YTI_PLAYLIST] Creating playlist for user: {}".format(str(user)))
            self.yti.create_playlist(user.user_name.replace(' ', '-'), user.user_id)
            # let's wait for our api request to take effect

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

    # deprecated :( this will be handled by a cron job
    # removes from user's YTI playlist
    async def _remove_from_yti_playlist(self, url, title=None, author=None):

        user = self.get_user(author)

        # should be preprocessed but im a scaredy cat
        if "youtube" not in url and "youtu.be" not in url:
            log.debug("[_REMOVE_FROM_YTI_PLAYLIST] Not a youtube URL: {}".format(url))
            return True

        try:
            #playlist_id = self.yti.lookup_playlist(user.user_id)
            video_id = self.yti.extract_youtube_video_id(url)
            self.yti.remove_video(user.user_id, video_id)
            return True

        except Exception as e:
            log.error("[_REMOVE_FROM_YTI_PLAYLIST] Failed to remove video {} for User: {}".format(title if title else url, user.user_id))
            self.email_util.send_exception(user.user_id, None, "[_REMOVE_FROM_YTI_PLAYLIST] " + str(e))

        return False
        
    def check_url(self, url):

        if url:
            if 'www.' in url and 'https://' not in url:
                url = 'https://' + url
            if '?t=' in url:
                url = url.split('?t=')[0]
            if '&t' in url or '&index' in url or '&list' in url:
                url = url.split('&')[0]
        return url
