from yti import YouTubeIntegration

yti = YouTubeIntegration()
        
def check_url(url):

    if url:
        if 'www.' in url and 'https://' not in url:
            url = 'https://' + url
        if '?t=' in url:
            url = url.split('?t=')[0]
        if '&t' in url or '&index' in url or '&list' in url:
            url = url.split('&')[0]
    return url

def get_user(author):

    user_id = None
    user_name = None
    with open('../data/users_list.json') as f:
        for line in f.readlines():
            if ' : ' in line:
                line = line.replace('\n', '')
                line = line.replace('\"', '', 4)
                if author in line.split(' : ')[0]:
                    user_name = line.split(' : ')[1]
                    user_id = line.split(' : ')[0]
    return user_id, user_name

# adds to the user's YTI playlist
def __add_to_autoplaylist(url, title=None, author=None):

    if author:
        musicbot_user_user_id, musicbot_user_user_name = get_user(author)
        if url:
            url = check_url(url)
            playlist_id = yti.lookup_playlist(musicbot_user_user_id)
            if playlist_id == None:
                if musicbot_user_user_name:
                    print("[__ADD_TO_AUTOPLAYLIST] Creating playlist for user: {}".format(musicbot_user_user_name))
                    yti.create_playlist(musicbot_user_user_name.replace(' ', '-'), musicbot_user_user_id)
                    #have to wait for our api request to take effect
                else:
                    print("[__ADD_TO_AUTOPLAYLIST] Name was null. ID: {}".format(musicbot_user_user_id))

            if "youtube" in url or "youtu.be" in url:
                video_id = yti.extract_youtube_video_id(url)
                if video_id:
                    video_playlist_id = yti.lookup_video(video_id, playlist_id)
                    if video_playlist_id == None:
                        yti.add_video(musicbot_user_user_id, video_id)
                    else:
                        print("Song {} already added to YTI Playlist {}".format(title, musicbot_user_user_name))
                else:
                    print("[__ADD_TO_AUTOPLAYLIST] video_id is None for url {}".format(url))
            else:
                print("[__ADD_TO_AUTOPLAYLIST] Not a youtube URL: {}".format(url))
        else:
            print("[__ADD_TO_AUTOPLAYLIST] url was null. Author: {}".format(musicbot_user_user_name))
    else:
        print("[__ADD_TO_AUTOPLAYLIST] author was null")

            # removes from user's YTI playlist
def __remove_from_autoplaylist(url, title=None, author=None):

    if type(url) == Music:
        url = url.get_url()
        print("[__REMOVE_FROM_AUTOPLAYLIST] URL {} passed is a Music obj, extracting URL".format(url))

    if author:
        if url:
            url = check_url(url)
            playlist_id = yti.lookup_playlist(author)
            if playlist_id:
                if "youtube" in url or "youtu.be" in url:
                    video_id = yti.extract_youtube_video_id(url)
                    if video_id:
                        if yti.lookup_video(video_id, playlist_id):
                            yti.remove_video(musicbot_user_user_id, video_id)
                        else:
                            print("[__REMOVE_FROM_AUTOPLAYLIST] Video {} is not in playlist {}".format(title, musicbot_user_user_name))
                    else:
                        print("[__REMOVE_FROM_AUTOPLAYLIST] video_id is None for url {}".format(title))
                else:
                    print("[__REMOVE_FROM_AUTOPLAYLIST] Not a youtube URL: {}".format(url))
            else:
                print("[__REMOVE_FROM_AUTOPLAYLIST] Playlist doesn't exist, can't delete from it. ID: {}".format(musicbot_user_user_id))
        else:
            print("[__REMOVE_FROM_AUTOPLAYLIST] url was null. Author: {}".format(musicbot_user_user_name))
    else:
        print("[__REMOVE_FROM_AUTOPLAYLIST] author was null")
    return False

if __name__ == "__main__":
    with open('../data/users_listCompare.json') as f:
        for line in f.readlines():
            if ' : ' in line:
                line = line.replace('\n', '')
                line = line.replace('\"', '', 4)
                url = line.split(' : ')[1]
                user_id = line.split(' : ')[0]
                print("URL {}, USER {}".format(url, user_id))

                __add_to_autoplaylist(url=url, title=None, author=user_id)
