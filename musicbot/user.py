import logging

from discord import utils
from .song import Song
log = logging.getLogger(__name__)

class User:

    """
        User keeps track of music information about a user.
    """

    def __init__(self, user_id, user_name, mood=None, yti_url=None):

        self._user_id = user_id
        self._user_name = user_name
        self._mood = mood
        self._yti_url = yti_url

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
    def yti_url(self):
        return self._yti_url

    @yti_url.setter
    def yti_url(self, new_yti_url):
        if new_yti_url != None:
            if type(new_yti_url) != str:
                new_yti_url = str(new_yti_url)
        else:
            log.warning("User tried to use yti_url setter but argument was None")
        self._yti_url = new_yti_url

    def __repr__(self):
        return self.user_name if self.user_name else str(self.user_id)
        