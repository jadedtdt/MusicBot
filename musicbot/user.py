from discord import utils

class User:

    """
        User keeps track of information about a user either for data science or for managing cooldowns to prevent abuse.
    """

    def __init__(self, user_id):
        self.canPlay = True
        self.canSkip = True
        self.canPlayNow = True
        self.canTagAdd = True

        self.user_id = user_id

        self.song_list = []

    ###########################################################################

    #   Getting from Class

    ###########################################################################

    def getSong(self, music_obj):
        for each_song in self.song_list:
            if each_song.getURL() == music_obj.getURL() or each_song.getURL() == music_obj.getURL():
                return each_song
        return None

    def getSongList(self):
        return self.song_list

    def getMood(self):
        return self.mood

    def getID(self):
        return self.user_id

    ###########################################################################

    #   Setting values

    ###########################################################################

    def setSongList(self, song_list):
        self.song_list = song_list

    def setMood(self, mood):
        self.mood = mood

    ###########################################################################

    #   Check if has

    ###########################################################################

    def hasSong(self, music_obj):
        for each_song in self.song_list:
            if each_song.getURL() == music_obj.getURL():
                return True

            if music_obj.getTitle() != None and each_song.getTitle() != None:
                if  music_obj.getTitle() in each_song.getTitle():
                    return True
        return False

    def hasMood(self, tag):
        return tag == self.mood

    ###########################################################################

    #   Adding to Class

    ###########################################################################

    def addSong(self, music_obj):
        self.song_list.append(music_obj)

    def addMood(self, tag):
        self.mood = tag

    ###########################################################################

    #   Removing from Class

    ###########################################################################

    def removeSong(self, music_obj):
        if self.hasSong(music_obj):
            toDelete = self.getSong(music_obj)
            if (toDelete in self.song_list):
                self.song_list.remove(toDelete)
                return True
        return False

    def __repr__(self):

        if self.song_list == None:
            songs = ""
        else:
            songs = str(self.song_list)

        return (self.user_id if self.user_id != None else "") + ": " + (self.mood if self.mood != None else "") + ". Songs: " + songs
