import logging
from datetime import datetime 

from discord import utils
from .song import Song
log = logging.getLogger(__name__)

class User:

    """
        User keeps track of music information about a user.
    """

    def __init__(self, user_id, user_name, mood=None, yti_url=None, updt_dt_tm=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), cret_dt_tm=datetime.now().strftime('%Y-%m-%d %H:%M:%S')):

        self._user_id = str(user_id)
        self._user_name = str(user_name)
        self._mood = mood
        self._yti_url = yti_url
        self._updt_dt_tm = str(updt_dt_tm)
        self._cret_dt_tm = str(cret_dt_tm)

    @property
    def user_id(self):
        return self._user_id

    @user_id.setter
    def user_id(self, new_user_id):
        if new_user_id:
            if type(new_user_id) != str:
                new_user_id = str(new_user_id)
        else:
            raise ValueError("User tried to use user_id setter but argument was None")
        self._user_id = new_user_id

    @property
    def user_name(self):
        return self._user_name

    @user_name.setter
    def user_name(self, new_user_name):
        if new_user_name:
            if type(new_user_name) != str:
                new_user_name = str(new_user_name)
        else:
            raise ValueError("User tried to use user_name setter but argument was None")
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
        
    @property
    def updt_dt_tm(self):
        return self._updt_dt_tm

    @updt_dt_tm.setter
    def updt_dt_tm(self, new_updt_dt_tm):
        if new_updt_dt_tm:
            if type(new_updt_dt_tm) != str:
                new_updt_dt_tm = str(new_updt_dt_tm)
        else:
            raise ValueError("Song tried to use updt_dt_tm setter but argument was None")
        self._new_updt_dt_tm = new_updt_dt_tm

    @property
    def cret_dt_tm(self):
        return self._cret_dt_tm

    @cret_dt_tm.setter
    def cret_dt_tm(self, new_cret_dt_tm):
        if new_cret_dt_tm:
            if type(new_cret_dt_tm) != str:
                new_cret_dt_tm = str(new_cret_dt_tm)
        else:
            raise ValueError("Song tried to use cret_dt_tm setter but argument was None")
        self._new_updt_dt_tm = new_cret_dt_tm

    def __repr__(self):
        return self.user_name if self.user_name else str(self.user_id)
        