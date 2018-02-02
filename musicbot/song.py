import logging

from .constants import DISCORD_MSG_CHAR_LIMIT, AUDIO_CACHE_PATH
from .config import Config, ConfigDefaults
from discord import User

log = logging.getLogger(__name__)

class Music:

    """
        Music keeps track of information about a song in our MusicBot.
    """

    def __init__(self, url, title=None, likers=None):
        config_file = ConfigDefaults.options_file
        self._config = Config(config_file)

        self._url = url

        if title:
            if type(title) != str:
                if type(title) == list:
                    title = " ".join(title)
                else:
                    raise ValueError("Title argument was of type: {} but needs to be list or str".format(type(tag)))
        self._title = title

        if likers:
            if type(likers) == list:
                self._likers = likers
            else:
                self._likers = [likers]
        else:
            self._likers = []

        self._play_count = 0
        self._tags = []
        self._volume = self._config.default_volume

    ###########################################################################

    #   Getting from Class

    ###########################################################################

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, new_url):
        if new_url != None:
            if type(new_url) != str:
                new_url = str(new_url)
        else:
            raise ValueError("Music tried to use url setter but argument was None")
        self._url = new_url

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, new_title):
        if new_title != None:
            if type(new_title) != str:
                new_title = str(new_title)
        self._title = new_title

    @property
    def likers(self):
        return self._likers

    @likers.setter
    def likers(self, new_likers):
        if new_likers != None:
            if type(new_likers) == str:
                # looks like a list as a string was passed, let's make it back into a list
                if ', ' in new_likers:
                    new_likers = new_likers.split(', ')
                else:
                    # hopefully this is just one user's id
                    new_likers = [new_likers]
            elif type(new_likers) != list:
                new_likers = list(new_likers)
        else:
            log.warning("Music tried to use likers setter but argument was None")
        self._likers = new_likers

    @property
    def play_count(self):
        return self._play_count

    @play_count.setter
    def play_count(self, new_play_count):
        if new_play_count != None:
            if type(new_play_count) != int:
                new_play_count = int(new_play_count)
        else:
            raise ValueError("Music tried to use play_count setter but argument was None")
        self._play_count = new_play_count

    @property
    def tags(self):
        return self._tags

    @tags.setter
    def tags(self, new_tags):
        if new_tags != None:
            if type(new_tags) == str:
                # looks like a list as a string was passed, let's make it back into a list
                if ', ' in new_tags:
                    new_tags = new_tags.split(', ')
                else:
                    # hopefully this is just one tag
                    new_tags = [new_tags]
            elif type(new_tags) != list:
                new_tags = list(new_tags)
        else:
            log.warning("Music tried to use tags setter but argument was None")
        self._tags = new_tags

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, new_volume):
        if new_volume != None:
            if type(new_volume) != float:
                new_volume = float(new_volume)
        else:
            raise ValueError("Music tried to use volume setter but argument was None")
        self._volume = new_volume

    ###########################################################################

    #   Check if has

    ###########################################################################

    def has_liker(self, liker):
        if liker != None:
            if type(liker) != str:                
                if type(liker) == int:
                    liker = str(liker)
                else:  
                    # if liker is musicbot User obj
                    if hasattr(liker, 'user_id'):
                        liker = liker.user_id
                    # if liker is discord User obj
                    elif hasattr(liker, 'id'):
                        liker = liker.id
        else:
            raise ValueError("Tried to call has_liker but arugment was None")
        return liker in self.likers

    def has_tag(self, tag):
        if tag != None:
            if type(tag) != str:
                if type(tag) == list:
                    has_all_tags = True
                    for each_tag in tag:
                        if each_tag:
                            if each_tag not in self.tags:
                                has_all_tags = False
                        else:
                            log.warning("[has_tag] Tag was None")
                    return has_all_tags
                else:
                    raise ValueError("Tag argument was of type: {} but needs to be list or str".format(type(tag)))
        else:
            log.warning("[has_tag] Tag was None")

        return tag in self.tags

    ###########################################################################

    #   Adding to Class

    ###########################################################################

    def add_play(self):
        self.play_count += 1

    def add_liker(self, liker):
        if liker != None:
            if type(liker) != str:                
                if type(liker) == int:
                    liker = str(liker)
                else:  
                    # if liker is musicbot User obj
                    if hasattr(liker, 'user_id'):
                        liker = liker.user_id
                    # if liker is discord User obj
                    elif hasattr(liker, 'id'):
                        liker = liker.id
        else:
            raise ValueError("Tried to call add_liker but argument was None")

        if not self.has_liker(liker):
            self.likers.append(liker)

    def add_tag(self, tag):
        if tag != None:
            if not self.has_tag(tag):
                self.tags.append(tag)
            else:
                log.warning("[add_tag] Tried to add a tag that was already added")
        else:
            raise ValueError("Tried to add tag but argument was None")

    ###########################################################################

    #   Removing from Class

    ###########################################################################

    def remove_play(self):
        if self.play_count > 0:
            self.play_count -= 1

    def remove_liker(self, liker):
        if liker != None:
            if type(liker) != str:                
                if type(liker) == int:
                    liker = str(liker)
                else:  
                    # if liker is musicbot User obj
                    if hasattr(liker, 'user_id'):
                        liker = liker.user_id
                    # if liker is discord User obj
                    elif hasattr(liker, 'id'):
                        liker = liker.id
        else:
            raise ValueError("Tried to call remove_liker but argument was None")

        if self.has_liker(liker):
            self.likers.remove(liker)

    def remove_tag(self, tag):
        if tag != None:
            if self.has_tag(tag):
                self.tags.remove(tag)
            else:
                log.warning("[remove_tag] Tried to remove a tag that didn't exist")
        else:
            raise ValueError("Tried to remove tag but argument was None")


    ###########################################################################

    #   Built-ins

    ###########################################################################

    def __repr__(self):
        return "Title: {title}, URL: {url}".format(
            title=getattr(self, 'title', "NO_TITLE"),
            url=getattr(self, 'url', "NO_URL"))

    def __hash__(self):
        return hash(self.url)

    #def __eq__(self, other):
    #    return self.url == other.url