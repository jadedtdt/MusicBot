from .constants import DISCORD_MSG_CHAR_LIMIT, AUDIO_CACHE_PATH, TITLE_URL_SEPARATOR, URL_LIKERS_SEPARATOR, LIKERS_DELIMETER

class music:
    def __init__(self, url, song_name, author, plays = 1):
        self.url = url
        self.name = song_name
        self.likers = [author]
        self.plays = plays
        self.tags = []
        self.volume = None

    ###########################################################################

    #   Getting from Class

    ###########################################################################
    def getURL(self):
        return self.url

    def getSong(self):
        return self.name

    def getLikers(self):
        return self.likers

    def getPlays(self):
        return self.plays

    def getTags(self):
        return self.tags

    def getVolume(self):
        return self.volume

    def getStore(self):
        temp = self.name + TITLE_URL_SEPARATOR + self.url + URL_LIKERS_SEPARATOR
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

    def setVolume(self, volume):
        self.volume = volume

    def __str__(self):
        return self.name + TITLE_URL_SEPARATOR + self.url
