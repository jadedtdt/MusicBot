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
        self.heard_length = 15
        self.heard_list = []
		
    ###########################################################################

    #   Getting from Class

    ###########################################################################
    '''
    def getSong(self, music_obj):
        if (type(music_obj) == str):
            music_obj()
        for each_song in self.song_list:
            if each_song.getURL() == music_obj.getURL() or each_song.getURL() == music_obj.getURL():
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

    def getHeard(self):
        return self.heard_list
		
    def getHeardLen(self):
        return self.heard_length
		
    ###########################################################################

    #   Setting values

    ###########################################################################
    def setSongList(self, song_list):
        self.song_list = song_list

    def setMood(self, mood):
        self.mood = mood
		
    def setHeardLen(self, heard_len):
        if self.heard_length > len(self.song_list):
            return False
        else:
            self.heard_length = heard_len
            return True
		
    def setupHeard(self):
        try:
            self.heard_list
        except:
            self.heard_list = []
            self.heard_length = 15

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

    def addHeard(self, music_obj):
        self.heard_list.append(music_obj)
        while len(self.heard_list) > self.heard_length:
            del self.heard_list[0]
		
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