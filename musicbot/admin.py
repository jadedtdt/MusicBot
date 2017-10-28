from .yti import YouTubeIntegration

from .config import Config, ConfigDefaults
from .utils import load_file, write_file, load_pickle, store_pickle

class Admin:
    def __init__(self, config_file):
        self.config = Config(config_file)

        # Autoplaylist
        self.autoplaylist = load_pickle(self.config.auto_playlist_pickle)

        # Users
        self.users_list = load_pickle(self.config.users_list_pickle)

        # Metadata
        self.metaData = {}
        self.wholeMetadata = load_file(self.config.metadata_file)

        for each_user in self.users_list:
            print(each_user)

        self.setupYTI()

    def setupYTI(self):
        pass