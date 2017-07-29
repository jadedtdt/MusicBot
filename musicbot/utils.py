import re
import aiohttp
import decimal
import unicodedata
import datetime
import os.path

import pickle

from hashlib import md5
from .constants import DISCORD_MSG_CHAR_LIMIT, LIKERS_DELIMETER



def load_file(filename, skip_commented_lines=True, comment_char='#'):
    try:
        with open(filename, encoding='utf8') as f:
            results = []
            for line in f:
                line = line.strip()

                if line and not (skip_commented_lines and line.startswith(comment_char)):
                    results.append(line)

            return results

    except IOError as e:
        print("Error loading", filename, e)
        return []

#deprecated for autoplaylist
def write_file(filename, contents):
    with open(filename, 'w', encoding='utf8') as f:
        for item in contents:
            f.write(str(item))
            f.write('\n')


########################
# is_latest_pickle
# 
# Checks if our pickle has changed since we last used it
#
# On change - return true
# No change - return false! we already have the latest version :)
#
# Precondition: pickle file exists
# Postcondition: n/a
#
# Returns: Boolean - True if lastest, false if not
########################
def is_latest_pickle(file_name, last_modified_ts):
    if (os.path.exists(file_name) and os.access(file_name, os.W_OK)):
        return os.path.getmtime(file_name) == last_modified_ts
    raise FileNotFoundError('APL Pickle could not be found')
    return False

########################
# store_pickle
# 
# Writes over our old pickle file, and returns the new apl and modified timestamp
#
# Precondition: have a local cache of a pickle file and the shared pickle exists
# Postcondition: local cache copied to shared pickle
#
# Returns: 'Return the time of last modification of path. The return value is a number giving the number of seconds since the epoch (see the time module)'
#           From https://docs.python.org/2/library/os.path.html
########################
def store_pickle(file_name, contents):
    pickle.dump(contents, open(file_name, "wb"), 4)
    return os.path.getmtime(file_name)

########################
# load_pickle
# 
# Loads the latest version of our pickle file
# Note: You should check that you match the last mod time
#       or you will overwrite any changes you have in your local APL!
#
# Precondition: have a local cache of a pickle file and the shared pickle exists
# Postcondition: shared pickle copied to local cache
########################
def load_pickle(file_name):
    if (os.path.exists(file_name) and os.access(file_name, os.W_OK)):
        return pickle.load(open(file_name, "rb"))
    else:
        raise FileNotFoundError('APL Pickle could not be found')
        return None

def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


def sane_round_int(x):
    return int(decimal.Decimal(x).quantize(1, rounding=decimal.ROUND_HALF_UP))


def paginate(content, *, length=DISCORD_MSG_CHAR_LIMIT, reserve=0):
    """
    Split up a large string or list of strings into chunks for sending to discord.
    """
    if type(content) == str:
        contentlist = content.split('\n')
    elif type(content) == list:
        contentlist = content
    else:
        raise ValueError("Content must be str or list, not %s" % type(content))

    chunks = []
    currentchunk = ''

    for line in contentlist:
        if len(currentchunk) + len(line) < length - reserve:
            currentchunk += line + '\n'
        else:
            chunks.append(currentchunk)
            currentchunk = ''

    if currentchunk:
        chunks.append(currentchunk)

    return chunks


async def get_header(session, url, headerfield=None, *, timeout=5):
    with aiohttp.Timeout(timeout):
        async with session.head(url) as response:
            if headerfield:
                return response.headers.get(headerfield)
            else:
                return response.headers


def md5sum(filename, limit=0):
    fhash = md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            fhash.update(chunk)
    return fhash.hexdigest()[-limit:]

########################
# sanitize_string
# 
# Cleans up a string by removing characters that might interefere when we split the string
#
# Precondition: string containing any possible characters
# Postcondition: string without characters possible included from using str(variable) like from lists or tuples
########################
def sanitize_string(string):
    clean = ""
    try:
        clean = str(string).replace("(", "").replace(")", "").replace("'", "").replace("[", "").replace("]", "").replace("\"", "")
    except:
        print("COPYRIGHT ISSUE")

    return clean

########################
# parse_string_delimeter
# 
# Replaces commas with semicolons so we can split on semicolons for the 'likers'
# We do this because a semicolon is a better delimeter when working with URLs
# Reference: http://www.sitepoint.com/forums/showthread.php?128801-Recommended-delimiter-for-list-of-URLs
#
# Precondition: string splitting IDs with commas. i.e. "1234, 3412, 2344"
# Postcondition: string splitting IDs with semicolons. i.e. "1234; 3412; 2344"
########################
def parse_string_delimeter(string):
    return str(string).replace(",", ";")

########################
# joinStr
# 
# When we have duplicate entries from merging autoplaylists, I believe the safest option is merge the two lists
# This function, written by Toaxt, does exactly that
#
# Precondition: two strings representing the likers for a url i.e. "1234; 2345; 3456", "1234; 4567"
# Postcondition: a single string representing the 'join' i.e. "1234; 2345; 3456; 4567"
########################
def joinStr(a, b):
    lista = a.split(LIKERS_DELIMETER)
    listb = b.split(LIKERS_DELIMETER)
    return LIKERS_DELIMETER.join(sorted(list(set(lista) | set(listb))))






