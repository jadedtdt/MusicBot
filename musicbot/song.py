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

    def __init__(self, url=None, title=None, play_count=0, volume=0.15):
        config_file = ConfigDefaults.options_file
        self._config = Config(config_file)

        self._url = url
        self._title = title
        self._play_count = play_count
        self._volume = volume

    ###########################################################################

    #   Getting from Class

    ###########################################################################

    @property
    def url(self):
        if not hasattr(self, '_last_played'):
            self._last_played = [datetime.now().strftime("%a, %B %d, %Y %I:%M %p"), datetime.now().strftime("%a, %B %d, %Y %I:%M %p")]
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

    ###########################################################################

    #   Built-ins

    ###########################################################################

    def __repr__(self):
        return self.title if self.title else self.url

    def __hash__(self):
        return hash(self.url)
