from .constants import DISCORD_MSG_CHAR_LIMIT, AUDIO_CACHE_PATH
from .config import Config, ConfigDefaults

class Music:

    def __init__(self, url, title=None, author=None):
        config_file = ConfigDefaults.options_file
        self.config = Config(config_file)

        if title != None:
            if type(title) == list:
                for each_word in title:
                    title += each_word + " "
        self.title = title
        self.url = url
        # check if already in list format
        if type(author) == list:
            self.likers = author
        else:
            self.likers = [author]

        self.plays = 0
        self.tags = []
        self.volume = self.config.default_volume

    ###########################################################################

    #   Getting from Class

    ###########################################################################

    def getTitle(self):
        return self.title

    def getURL(self):
        return self.url

    def getLikers(self):
        return self.likers

    # play count, number of times played
    def getPlays(self):
        return self.plays

    def getTags(self):
        return self.tags

    def getVolume(self):
        return self.volume

    ###########################################################################

    #   Check if has

    ###########################################################################

    # takes a discord user id
    def hasLiker(self, liker):
        #force int
        if type(liker) == int:
            liker = str(liker)
        return liker in self.likers

    def hasTag(self, tag):
        return tag in self.tags

    ###########################################################################

    #   Adding to Class

    ###########################################################################

    def addPlay(self):
        self.plays += 1

    # takes a discord user id
    def addLiker(self, liker):
        #force int
        if type(liker) == int:
            liker = str(liker)
        if not self.hasLiker(liker):
            self.likers.append(liker)

    def addTag(self, tag):
        self.tags.append(tag)

    def setTitle(self, title):
        self.title = title

    def setURL(self, url):
        self.url = url

    def setVolume(self, volume):
        self.volume = volume

    def __repr__(self):
        return ("" if self.url == None else self.url) + " --- " + ("" if self.title ==  None else self.title)

    ###########################################################################

    #   Removing from Class

    ###########################################################################

    def removePlay(self):
        if self.plays > 0:
            self.plays -= 1

    # takes a discord user id
    def removeLiker(self, liker):
        #force int
        if type(liker) == int:
            liker = str(liker)
        if self.hasLiker(liker):
            self.likers.remove(liker)

    def removeTag(self, tag):
        if self.hasTag(tag):
            self.tags.remove(tag)