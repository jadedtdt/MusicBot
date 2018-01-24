from discord import utils
from .musicClass import Music

class User:

    """
        User keeps track of information about a user either for data science or for managing cooldowns to prevent abuse.
    """

    def __init__(self, user_id, user_name):
        self.can_play = True
        self.can_skip = True
        self.can_playnow = True
        self.can_tag_add = True

        self.user_id = user_id
        self.user_name = user_name

        self.mood = None

        self.song_list = []

    ###########################################################################

    #   Getting from Class

    ###########################################################################
    '''
    def getSong(self, music_obj):

        # if given a string, force into music object type
        if (type(music_obj) != Music):

            if "http" in music_obj:
                music_obj = Music(music_obj)
            else:
                music_obj = Music(None, music_obj)

        for each_song in self.song_list:
            if music_obj.getURL() is not None and music_obj.getURL() == each_song.getURL():
                return each_song
            if music_obj.getTitle() is not None and music_obj.getTitle().lower() in each_song.getTitle().lower():
                return each_song
        return None
    '''

    def getSongList(self):
        return self.song_list

    def getMood(self):
        return self.mood

    def getID(self):
        return self.user_id

    def getName(self):
        return self.user_name

    ###########################################################################

    #   Setting values

    ###########################################################################
    def setSongList(self, song_list):
        self.song_list = song_list

    def setMood(self, mood):
        self.mood = mood

    def setID(self, user_id):
        self.user_id = user_id

    def setName(self, name):
        self.user_name = user_name

    ###########################################################################

    #   Check if has

    ###########################################################################
    def hasSong(self, url):
        if type(url) == Music:
            url = url.getURL()
        return url in self.song_list

    def hasMood(self, tag):
        return tag == self.mood

    ###########################################################################

    #   Adding to Class

    ###########################################################################
    def addSong(self, url):
        if not self.hasSong(url):
            self.song_list.append(url)
            return True
        return False

    # same as setMood for now
    def addMood(self, tag):
        self.mood = tag

    ###########################################################################

    #   Removing from Class

    ###########################################################################
    def removeSong(self, url):
        if self.hasSong(url):
            self.song_list.remove(url)
            return True
        return False

    def __repr__(self):
        return "Name: {name}, ID: {id}".format(
            name=getattr(self, 'user_name', "NO_NAME"),
            id=getattr(self, 'user_id', "NO_ID"))
