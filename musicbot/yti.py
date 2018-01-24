import httplib2
import os
import sys

from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret. You can acquire an OAuth 2.0 client ID and client secret from
# the Google Cloud Console at
# https://cloud.google.com/console.
# Please ensure that you have enabled the YouTube Data API for your project.
# For more information about using OAuth2 to access the YouTube Data API, see:
#   https://developers.google.com/youtube/v3/guides/authentication
# For more information about the client_secrets.json file format, see:
#   https://developers.google.com/api-client-library/python/guide/aaa_client_secrets

class YouTubeIntegration:

    def __init__(self):
        # The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
        # the OAuth 2.0 information for this application, including its client_id and
        # client_secret. You can acquire an OAuth 2.0 client ID and client secret from
        # the {{ Google Cloud Console }} at
        # {{ https://cloud.google.com/console }}.
        # Please ensure that you have enabled the YouTube Data API for your project.
        # For more information about using OAuth2 to access the YouTube Data API, see:
        #   https://developers.google.com/youtube/v3/guides/authentication
        # For more information about the client_secrets.json file format, see:
        #   https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
        self.CLIENT_SECRETS_FILE = "client_secrets.json"

        # This variable defines a message to display if the CLIENT_SECRETS_FILE is
        # missing.
        self.MISSING_CLIENT_SECRETS_MESSAGE = """
        WARNING: Please configure OAuth 2.0

        To make this sample run you will need to populate the client_secrets.json file
        found at:

           %s

        with information from the {{ Cloud Console }}
        {{ https://cloud.google.com/console }}

        For more information about the client_secrets.json file format, please visit:
        https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
        """ % os.path.abspath(os.path.join(os.path.dirname(__file__), self.CLIENT_SECRETS_FILE))

        # This OAuth 2.0 access scope allows for full read/write access to the
        # authenticated user's account.
        self.YOUTUBE_READ_WRITE_SCOPE = "https://www.googleapis.com/auth/youtube"
        self.YOUTUBE_API_SERVICE_NAME = "youtube"
        self.YOUTUBE_API_VERSION = "v3"

        self.youtube = self.get_authenticated_service()

    # Authorize the request and store authorization credentials.
    def get_authenticated_service(self):
        flow = flow_from_clientsecrets(self.CLIENT_SECRETS_FILE,
            message=self.MISSING_CLIENT_SECRETS_MESSAGE,
            scope=self.YOUTUBE_READ_WRITE_SCOPE)

        storage = Storage("%s-oauth2.json" % sys.argv[0])
        credentials = storage.get()

        if credentials is None or credentials.invalid:
            credentials = run_flow(flow, storage)

        # Trusted testers can download this discovery document from the developers page
        # and it should be in the same directory with the code.
        return build(self.YOUTUBE_API_SERVICE_NAME, self.YOUTUBE_API_VERSION, http=credentials.authorize(httplib2.Http()))

    # nate wrote this
    def check_url(self, url):
        if 'www.' in url and 'https://' not in url:
            url = 'https://' + url
        if '?t=' in url:            
            return url.split('?')[0]
        if '&t' in url or '&index' in url or '&list' in url:
            return url.split('&')[0]
        return url

    #extracts the uid from the url
    def extract_youtube_uid(self, full_url):
        full_url = self.check_url(full_url)
        if "youtube" in full_url:
            if "watch?v=" in full_url:
                return full_url.split("watch?v=")[1]
            else:
                print("Probably a playlist URL or something")
        elif "youtu.be/" in full_url:            
            if "youtu.be/" in full_url:
                return full_url.split("youtu.be/")[1]
        return None

    def create_playlist(self, discord_username, suffix=""):
        DELIMETER = ":"
        # This code creates a new, private playlist in the authorized user's channel.
        playlists_insert_response = self.youtube.playlists().insert(
            part="snippet,status",
            body=dict(
                snippet=dict(
                    title=discord_username + ("" if suffix == "" else DELIMETER + suffix) ,
                    description="A playlist created with the YouTube API v3 for Jadedtdt's MusicBot"
                ),
                status=dict(
                    privacyStatus="public"
                )
            )
        ).execute()

    # Searches for a playlist ID based on a name
    def remove_playlist(self, name):
        playlist_id = self.lookup_playlist(name)
        if playlist_id != None:
            self.youtube.playlists().delete(
                id=playlist_id
            ).execute()
        else:
            print("ERROR: Playlist not found - " + name)


    # Looks up a playlist by name and returns the id
    def lookup_playlist(self, name):
        playlist_id=None
        playlists = self.youtube.playlists().list(
                part="snippet",
                mine=True
        ).execute()

        for each_playlist in playlists["items"]:
            if each_playlist["snippet"]["title"] == name:
                playlist_id = each_playlist["id"]

        return playlist_id

    # Uses a video id and a playlist id to get the video-playlist id
    def lookup_video(self, video_id, playlist_id):
        video_playlist_id = None
        items = self.youtube.playlistItems().list(
            part = "snippet",
            playlistId = playlist_id
        ).execute()

        for each_item in items["items"]:
            if each_item["snippet"]["resourceId"]["videoId"] == video_id:
                video_playlist_id = each_item["id"]

        return video_playlist_id

    # Takes a playlist by name and a videos id
    def add_video(self, playlist, video_id):
        playlist_id = self.lookup_playlist(playlist)
        if playlist_id != None:
            video_playlist_id = self.lookup_video(video_id, playlist_id)
            if video_playlist_id == None:
                self.youtube.playlistItems().insert(
                    part = "snippet",
                    body = dict(
                        snippet = dict(
                            playlistId = playlist_id,
                            resourceId = dict(
                                kind = "youtube#video",
                                videoId = video_id
                            ),
                        )
                    )
                ).execute()
            else:
                print("WARNING: Playlist already contains song - " + playlist + ", " + video_id)
        else:
            print("ERROR: Playlist not found - " + name)

    # Takes a playlist by name and a videos id
    def remove_video(self, playlist, video_id):
        playlist_id = lookup_playlist(playlist)
        video_playlist_id = lookup_video(video_id, playlist_id)
        if playlist_id != None:
            if video_playlist_id != None:
                print(video_playlist_id)
                self.youtube.playlistItems().delete(
                    id = video_playlist_id
                ).execute()
            else:
                print("ERROR: Playlist does not contain video - " + playlist + ", " + video_id)
        else:
            print("ERROR: Playlist not found - " + name)


#if __name__ == '__main__':
    #args = argparser.parse_args()
    #youtube = get_authenticated_service(args)
    #create_playlist("jadedtdt")
    #remove_playlist("jadedtdt")
    #add_video("jadedtdt", "7pilppVBPrE")
    #remove_video("jadedtdt", "7pilppVBPrE")