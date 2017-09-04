import sys
import decimal
import logging
import aiohttp

import os.path
import pickle

from hashlib import md5
from .constants import DISCORD_MSG_CHAR_LIMIT

log = logging.getLogger(__name__)

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
# Returns: 'Return the time of last modification of path. The return value is a number giving the number of seconds since the epoch (see the time module)'
#           From https://docs.python.org/2/library/os.path.html
########################
def get_latest_pickle_mtime(file_name):
    if (os.path.exists(file_name) and os.access(file_name, os.W_OK)):
        return float(os.path.getmtime(file_name))
    raise FileNotFoundError('APL Pickle could not be found')

########################
# store_pickle
# 
# Writes over our old pickle file, and returns the new apl and modified timestamp
#
# Precondition: have a local cache of a pickle file and the shared pickle exists
# Postcondition: local cache copied to shared pickle
#
########################
def store_pickle(file_name, contents):
    pickle.dump(contents, open(file_name, "wb"), 4)

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
    raise FileNotFoundError('APL Pickle could not be found')

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


def fixg(x, dp=2):
    return ('{:.%sf}' % dp).format(x).rstrip('0').rstrip('.')


def ftimedelta(td):
    p1, p2 = str(td).rsplit(':', 1)
    return ':'.join([p1, str(int(float(p2)))])


def safe_print(content, *, end='\n', flush=True):
    sys.stdout.buffer.write((content + end).encode('utf-8', 'replace'))
    if flush: sys.stdout.flush()


def avg(i):
    return sum(i) / len(i)


def objdiff(obj1, obj2, *, access_attr=None, depth=0):
    changes = {}

    if access_attr is None:
        attrdir = lambda x: x

    elif access_attr == 'auto':
        if hasattr(obj1, '__slots__') and hasattr(obj2, '__slots__'):
            attrdir = lambda x: getattr(x, '__slots__')

        elif hasattr(obj1, '__dict__') and hasattr(obj2, '__dict__'):
            attrdir = lambda x: getattr(x, '__dict__')

        else:
            # log.everything("{}{} or {} has no slots or dict".format('-' * (depth+1), repr(obj1), repr(obj2)))
            attrdir = dir

    elif isinstance(access_attr, str):
        attrdir = lambda x: list(getattr(x, access_attr))

    else:
        attrdir = dir

    # log.everything("Diffing {o1} and {o2} with {attr}".format(o1=obj1, o2=obj2, attr=access_attr))

    for item in set(attrdir(obj1) + attrdir(obj2)):
        try:
            iobj1 = getattr(obj1, item, AttributeError("No such attr " + item))
            iobj2 = getattr(obj2, item, AttributeError("No such attr " + item))

            # log.everything("Checking {o1}.{attr} and {o2}.{attr}".format(attr=item, o1=repr(obj1), o2=repr(obj2)))

            if depth:
                # log.everything("Inspecting level {}".format(depth))
                idiff = objdiff(iobj1, iobj2, access_attr='auto', depth=depth - 1)
                if idiff:
                    changes[item] = idiff

            elif iobj1 is not iobj2:
                changes[item] = (iobj1, iobj2)
                # log.everything("{1}.{0} ({3}) is not {2}.{0} ({4}) ".format(item, repr(obj1), repr(obj2), iobj1, iobj2))

            else:
                pass
                # log.everything("{obj1}.{item} is {obj2}.{item} ({val1} and {val2})".format(obj1=obj1, obj2=obj2, item=item, val1=iobj1, val2=iobj2))

        except Exception as e:
            # log.everything("Error checking {o1}/{o2}.{item}".format(o1=obj1, o2=obj2, item=item), exc_info=e)
            continue

    return changes

def color_supported():
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

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
def join_str(a, b):
    lista = a.split(LIKERS_DELIMETER)
    listb = b.split(LIKERS_DELIMETER)
    return LIKERS_DELIMETER.join(sorted(list(set(lista) | set(listb))))