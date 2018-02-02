import logging

from discord import utils
from .song import Music
log = logging.getLogger(__name__)

class User:

    """
        User keeps track of music information about a user.
    """

    def __init__(self, user_id, user_name):

        self._user_id = user_id
        self._user_name = user_name

        self._mood = None

        self._song_list = []
        self._heard_length = 15
        self._heard_list = []

    @property
    def user_id(self):
        return self._user_id

    @user_id.setter
    def user_id(self, new_user_id):
        if new_user_id != None:
            if type(new_user_id) != str:
                new_user_id = str(new_user_id)
        else:
            log.warning("User tried to use user_id setter but argument was None")
        self._user_id = new_user_id

    @property
    def user_name(self):
        return self._user_name

    @user_name.setter
    def user_name(self, new_user_name):
        if new_user_name != None:
            if type(new_user_name) != str:
                new_user_name = str(new_user_name)
        else:
            log.warning("User tried to use user_name setter but argument was None")
        self._user_name = new_user_name

    @property
    def mood(self):
        return self._mood

    @mood.setter
    def mood(self, new_mood):
        if new_mood != None:
            if type(new_mood) != str:
                new_mood = str(new_mood)
        else:
            log.warning("User tried to use mood setter but argument was None")
        self._mood = new_mood
		
    @property
    def song_list(self):
        return self._song_list

    @song_list.setter
    def song_list(self, new_song_list):
        if new_song_list != None:
            if type(new_song_list) == str:
                assert ', ' in new_song_list
                new_song_list = new_song_list.split(', ')
            elif type(new_song_list) != list:
                new_song_list = list(new_song_list)
        else:
            log.warning("User tried to use song_list setter but argument was None")
        self._song_list = new_song_list

    @property
    def heard_length(self):
        return self._heard_length

    @heard_length.setter
    def heard_length(self, new_heard_length):
        if new_heard_length != None:
            if type(new_heard_length) != int:
                new_heard_length = int(new_heard_length)
        else:
            raise ValueError("User tried to use heard_length setter but argument was None")

        if new_heard_length > len(self.song_list):
            log.error("Heard length cannot exceed the length of the user's song list: " + str(len(self.song_list)))
            new_heard_length = len(self.song_list)
        else:
            self._heard_length = new_heard_length

    @property
    def heard_list(self):
        return self._heard_list

    @heard_list.setter
    def heard_list(self, new_heard_list):
        if new_heard_list != None:
            if type(new_heard_list) == str:
                assert ', ' in new_heard_list
                new_heard_list = new_heard_list.split(', ')
            elif type(new_heard_list) != list:
                new_heard_list = list(new_heard_list)
        else:
            log.warning("User tried to use heard_list setter but argument was None")
            new_heard_list = []

        self._heard_list = new_heard_list

    ###########################################################################

    #   Setting up the Class

    ###########################################################################
				
    def setup_heard(self):
        try:
            self.heard_list
        except:
            self.heard_list = []
            self.heard_length = 15

    ###########################################################################

    #   Check if has

    ###########################################################################

    def has_song(self, url):
        if hasattr(url, 'url'):
            url = url.url
        return url in self.song_list

    def has_mood(self, tag):
        return tag == self.mood

    ###########################################################################

    #   Adding to Class

    ###########################################################################

    def add_song(self, url):
        if not self.has_song(url):
            self.song_list.append(url)
            return True
        return False

    def add_heard(self, music_obj):
        if self.heard_list != None:
            self.heard_list.append(music_obj)
            while len(self.heard_list) > self.heard_length:
                del self.heard_list[0]
        else:
            raise AttributeError("Tried to add a heard song but heard_list was None")
		
    ###########################################################################

    #   Removing from Class

    ###########################################################################

    def remove_song(self, url):
        if self.has_song(url):
            self.song_list.remove(url)
            return True
        return False

    def __repr__(self):
        return "Name: {name}, ID: {id}".format(
            name=getattr(self, 'user_name', "NO_NAME"),
            id=getattr(self, 'user_id', "NO_ID"))