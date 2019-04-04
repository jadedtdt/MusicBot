import logging
from datetime import datetime 

from .constants import DISCORD_MSG_CHAR_LIMIT, AUDIO_CACHE_PATH
from .config import Config, ConfigDefaults
from discord import User

log = logging.getLogger(__name__)

class Song:

    """
        Song keeps track of information about a song in our MusicBot.
    """

    def __init__(self, url, title=None, play_count=0, volume=0.15, updt_dt_tm=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), cret_dt_tm=datetime.now().strftime('%Y-%m-%d %H:%M:%S')):
        config_file = ConfigDefaults.options_file
        self._config = Config(config_file)

        self._url = str(url)
        self._title = title
        self._play_count = int(play_count)
        self._volume = float(volume)
        self._updt_dt_tm = str(updt_dt_tm)
        self._cret_dt_tm = str(cret_dt_tm)

    ###########################################################################

    #   Getting from Class

    ###########################################################################

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, new_url):
        if new_url:
            if type(new_url) != str:
                new_url = str(new_url)
        else:
            raise ValueError("Song tried to use url setter but argument was None")
        self._url = new_url

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, new_title):
        if new_title:
            if type(new_title) != str:
                new_title = str(new_title)
        else:
            log.warning("Song tried to use title setter but argument was None")
        self._title = new_title

    @property
    def play_count(self):
        return self._play_count

    @play_count.setter
    def play_count(self, new_play_count):
        if new_play_count:
            if type(new_play_count) != int:
                new_play_count = int(new_play_count)
        else:
            raise ValueError("Song tried to use play_count setter but argument was None")
        self._play_count = new_play_count

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, new_volume):
        if new_volume:
            if type(new_volume) != float:
                new_volume = float(new_volume)
        else:
            raise ValueError("Song tried to use volume setter but argument was None")
        self._volume = new_volume

    @property
    def updt_dt_tm(self):
        return self._updt_dt_tm

    @updt_dt_tm.setter
    def updt_dt_tm(self, new_updt_dt_tm):
        if new_updt_dt_tm:
            if type(new_updt_dt_tm) != str:
                new_updt_dt_tm = str(new_updt_dt_tm)
        else:
            raise ValueError("Song tried to use updt_dt_tm setter but argument was None")
        self._updt_dt_tm = new_updt_dt_tm

    @property
    def cret_dt_tm(self):
        return self._cret_dt_tm

    @cret_dt_tm.setter
    def cret_dt_tm(self, new_cret_dt_tm):
        if new_cret_dt_tm:
            if type(new_cret_dt_tm) != str:
                new_cret_dt_tm = str(new_cret_dt_tm)
        else:
            raise ValueError("Song tried to use cret_dt_tm setter but argument was None")
        self._cret_dt_tm = new_cret_dt_tm

    ###########################################################################

    #   Built-ins

    ###########################################################################

    def __repr__(self):
        return self.title if self.title else self.url

    def __hash__(self):
        return hash(self.url)
