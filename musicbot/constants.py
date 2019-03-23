import os.path

MAIN_VERSION = '1.9.6'
SUB_VERSION = '-review'
VERSION = MAIN_VERSION + SUB_VERSION

AUDIO_CACHE_PATH = os.path.join(os.getcwd(), '../../prod/MusicBot/audio_cache')
BACKUP_PATH = os.path.join(os.getcwd(), '../../prod/MusicBot/data/backup')
DATA_PATH = os.path.join(os.getcwd(), '../../prod/MusicBot/data')
DISCORD_MSG_CHAR_LIMIT = 2000

LIKERS_DELIMETER = "; "
