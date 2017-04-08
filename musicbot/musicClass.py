from .constants import DISCORD_MSG_CHAR_LIMIT, AUDIO_CACHE_PATH, TITLE_URL_SEPARATOR, URL_LIKERS_SEPARATOR, LIKERS_DELIMETER
from .config import Config, ConfigDefaults

class Music:

    def __init__(self, title, url, author=None):
        config_file = ConfigDefaults.options_file
        self.config = Config(config_file)

        self.title = title
        self.url = url
        # check if already in list format
        if (author == list(author)):
            self.likers = author
        else:
            self.likers = [author]

            # if "[" in author or "]" in author

        self.plays = 1
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

    # do we really even need this?
    def getStore(self):
        temp = self.title + TITLE_URL_SEPARATOR + self.url + URL_LIKERS_SEPARATOR
        for liker in self.likers:
            temp =+ str(liker) + LIKERS_DELIMETER
        return temp[:-2]

    ###########################################################################

    #   Check if has

    ###########################################################################
    def hasLiker(self, author):
        if author in self.likers:
            return True
        else:
            return False

    def hasTag(self, tag):
        if tag in self.tags:
            return True
        else:
            return False

    ###########################################################################

    #   Adding to Class

    ###########################################################################
    def addPlay(self):
        self.plays += 1

    def addLiker(self, liker):
        self.likers.append(liker)

    def addTag(self, tag):
        self.tags.append(tag)

    def setTitle(self, title):
        self.title = title

    def setURL(self, url):
        self.url = url

    def setVolume(self, volume):
        self.volume = volume

    def __str__(self):
        return self.title + TITLE_URL_SEPARATOR + self.url

    ###########################################################################

    #   Removing from Class

    ###########################################################################
    def removePlay(self):
        if self.plays > 0:
            self.plays -= 1

    def removeLiker(self, liker):
        if self.hasLiker(liker):
            self.likers.remove(liker)

    def removeTag(self, tag):
        if self.hasTag(tag):
            self.tags.remove(tag)