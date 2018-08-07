import httplib2
import logging
import os
import sys

from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow
log = logging.getLogger(__name__)

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
        self.CLIENT_SECRETS_FILE = "secrets/client_secrets.json"

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

    # Authorize the request and store authentication credentials.
    def get_authenticated_service(self):
        flow = flow_from_clientsecrets(self.CLIENT_SECRETS_FILE,
            message=self.MISSING_CLIENT_SECRETS_MESSAGE,
            scope=self.YOUTUBE_READ_WRITE_SCOPE)

        storage = Storage("secrets/%s-oauth2.json" % sys.argv[0])
        credentials = storage.get()

        if credentials is None or credentials.invalid:
            credentials = run_flow(flow, storage)

        # Trusted testers can download this discovery document from the developers page
        # and it should be in the same directory with the code.
        return build(self.YOUTUBE_API_SERVICE_NAME, self.YOUTUBE_API_VERSION, http=credentials.authorize(httplib2.Http()))

    def check_url(self, url):

        if url:
            if 'www.' in url and 'https://' not in url:
                url = 'https://' + url
            if '?t=' in url:            
                url = url.split('?t=')[0]
            if '&t' in url or '&index' in url or '&list' in url:
                url = url.split('&')[0]
        return url

    #extracts the uid from the url
    def extract_youtube_video_id(self, full_url):

        full_url = self.check_url(full_url)
        if "youtube" in full_url:
            if "watch?v=" in full_url:
                return full_url.split("watch?v=")[1]
            else:
                log.debug("[EXTRACT_YOUTUBE_VIDEO_ID] Probably a playlist URL or something {}".format(full_url))
        elif "youtu.be/" in full_url:            
            if "youtu.be/" in full_url:
                return full_url.split("youtu.be/")[1]
        return None

    # Creates a new, private playlist in the authenticated user's (Elegiggle MusicBot) channel.
    def create_playlist(self, user_name, user_id):

        DELIMETER = ":"
        if user_name:
            if user_id:
                try:
                    self.youtube.playlists().insert(
                        part="snippet,status",
                        body=dict(
                            snippet=dict(
                                title=user_name,
                                description=user_id
                            ),
                            status=dict(
                                privacyStatus="public"
                            )
                        )
                    ).execute()
                except Exception as e:
                    log.error("[CREATE_PLAYLIST] Failed to create playlist for User {}".format(user_id))
                    self.email_util.send_exception(user_name if user_name else user_id, None, "[YTI][CREATE_PLAYLIST] " + str(e))
            else:
                log.error("[CREATE_PLAYLIST] No user_id given")
        else:
            log.error("[CREATE_PLAYLIST] No user_name given")

    # Searches for a playlist ID based on a user id
    def remove_playlist(self, user_id):

        if user_id:
            playlist_id = self.lookup_playlist(user_id)
            if playlist_id:
                try:
                    self.youtube.playlists().delete(
                        id=playlist_id
                    ).execute()
                except Exception as e:
                    log.error("[REMOVE_PLAYLIST] Failed to remove playlist for User: {}".format(user_id))
                    self.email_util.send_exception(user_name if user_name else user_id, None, "[YTI][REMOVE_PLAYLIST] " + str(e))
            else:
                log.error("[REMOVE_PLAYLIST] Playlist not found - {}".format(user_id))
        else:
            log.error("[REMOVE_PLAYLIST] user_id was null")

    # Looks up a playlist by user id and returns the youtube playlist id
    def lookup_playlist(self, user_id):

        playlist_id=None
        if user_id:
            playlists_request = self.youtube.playlists().list(
                part="snippet",
                mine=True,
                maxResults=50
            )

            while playlists_request:
                playlists_response = playlists_request.execute()
                if playlists_response:
                    if playlists_response["items"]:
                        for each_playlist in playlists_response["items"]:
                            if each_playlist["snippet"]["description"] == user_id:
                                playlist_id = each_playlist["id"]
                    else:
                        log.error("[LOOKUP_PLAYLIST] There were no playlists to fetch - {}".format(user_id))
                else:
                    log.error("[LOOKUP_PLAYLIST] Failed to execute the request")

                playlists_request = self.youtube.playlists().list_next(playlists_request, playlists_response)
        else:
            log.error("[LOOKUP_PLAYLIST] user_id was null")


        return playlist_id

    # Updates the playlists name to users latest name
    def update_playlist_name(self, user_id, user_name):

        if user_id:
            if user_name:
                playlist_id = self.lookup_playlist(user_id)
                if playlist_id:
                    try:
                        self.youtube.playlists().update(
                            part="snippet",
                            body=dict(
                                id=playlist_id,
                                snippet=dict(
                                    title=user_name + ("" if suffix == "" else DELIMETER + suffix)
                                )
                            )
                        ).execute()
                    except Exception as e:
                        log.error("[UPDATE_PLAYLIST_NAME] Failed to update playlist for User: {}".format(user_name))
                        self.email_util.send_exception(user_name if user_name else user_id, None, "[YTI][UPDATE_PLAYLIST_NAME] " + str(e))

                else:
                    log.error("[UPDATE_PLAYLIST_NAME] Playlist not found - {}".format(user_id))
            else:
                log.error("[UPDATE_PLAYLIST_NAME] user_name was null. ID: {}".format(user_id))
        else:
            log.error("[UPDATE_PLAYLIST_NAME] user_id was null")

    # Updates the playlists name to users latest name
    # True if needs updated, False if doesn't
    def check_playlist_name(self, user_id, user_name, playlist_id=None):

        needsChanged = True
        if user_id:
            if user_name:
                if not playlist_id:
                    playlist_id = self.lookup_playlist(user_id)

                if playlist_id:
                    playlists_request = self.youtube.playlists().list(
                        part="snippet",
                        mine=True,
                        maxResults=50,
                        id=playlist_id
                        )
                    while playlists_request:
                        playlists_response = playlists_request.execute()

                        if playlists_response:
                            for each_playlist in playlists_response["items"]:
                                if each_playlist["snippet"]["description"] == user_id:
                                    log.debug("[CHECK_PLAYLIST_NAME] Found playlist {} for user {}", each_playlist["snippet"]["title"], user_name)
                                    needsChanged = (each_playlist["snippet"]["title"] != user_name)
                                    return needsChanged
                        else:
                            log.error("[CHECK_PLAYLIST_NAME] Failed to execute the request")

                        playlists_request = self.youtube.playlistItems().list_next(playlists_request, playlists_response)
                    log.warning("[CHECK_PLAYLIST_NAME] Couldn't find playlist matching user! {}:{}".format(user_id, user_name))

                log.warning("[CHECK_PLAYLIST_NAME] playlist_id was null. ID: {}".format(user_id, user_name))
            else:
                log.error("[CHECK_PLAYLIST_NAME] user_name was null. ID: {}".format(user_id))
        else:
            log.error("[CHECK_PLAYLIST_NAME] user_id was null")

        return needsChanged

    # Uses a video id and a playlist id to get the video-playlist id
    def lookup_video(self, video_id, playlist_id):

        video_playlist_id = None
        if video_id:
            if playlist_id:
                items_request = self.youtube.playlistItems().list(
                    part = "snippet",
                    playlistId = playlist_id,
                    maxResults=50
                )

                while items_request:
                    items_response = items_request.execute()
                    if items_response:
                        if items_response["items"]:
                            for each_item in items_response["items"]:
                                if each_item["snippet"]["resourceId"]["videoId"] == video_id:
                                    video_playlist_id = each_item["id"]
                        else:
                            log.debug("[LOOKUP_VIDEO] There were no videos to fetch - {}".format(video_id))

                        items_request = self.youtube.playlistItems().list_next(items_request, items_response)

                if not video_playlist_id:
                    log.debug("[LOOKUP_VIDEO] Couldn't find video - {}".format(video_id))
            else:
                log.error("[LOOKUP_VIDEO] playlist_id was null. Video ID: {}".format(video_id))
        else:
            log.error("[LOOKUP_VIDEO] video_id was null")

        return video_playlist_id

    # Adds a video by user id and a video's id
    def add_video(self, user_id, video_id):

        if user_id:
            if video_id:
                playlist_id = self.lookup_playlist(user_id)
                if playlist_id:
                    try:
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
                    except Exception as e:
                        log.error("[ADD_VIDEO] Failed to add video {} for User: {}".format(video_id, user_id))
                        self.email_util.send_exception(user_id, None, "[YTI][ADD_VIDEO] " + str(e))
                else:
                    log.error("[ADD_VIDEO] Playlist not found - {}".format(user_id))
            else:
                log.error("[ADD_VIDEO] video_id was null. ID: {}".format(user_id))
        else:
            log.error("[ADD_VIDEO] user_id was null")

    # Takes a playlist by user_id and a videos id. Note: this is NOT the video-playlist id!
    def remove_video(self, user_id, video_id):

        if user_id:
            if video_id:
                playlist_id = self.lookup_playlist(user_id)
                if playlist_id:
                    video_playlist_id = self.lookup_video(video_id, playlist_id)
                    if video_playlist_id:
                        try:
                            self.youtube.playlistItems().delete(
                                id = video_playlist_id,
                            ).execute()
                        except Exception as e:
                            log.error("[REMOVE_VIDEO] Failed to remove video {} for User: {}".format(video_id, user_id))
                            self.email_util.send_exception(user_id, None, "[YTI][REMOVE_VIDEO] " + str(e))
                    else:
                        log.error("[REMOVE_VIDEO] Playlist does not contain video - {},{}".format(user_id, video_id))
                else:
                    log.error("[REMOVE_VIDEO] Playlist not found {}".format(user_id))
            else:
                log.error("[REMOVE_VIDEO] video_id was null. ID: {}".format(user_id))
        else:
            log.error("[REMOVE_VIDEO] user_id was null")
