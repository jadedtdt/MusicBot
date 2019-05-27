from musicbot.autoplaylist import AutoPlaylist
from musicbot.sqlfactory import SqlFactory
from musicbot.song import Song
from musicbot.user import User

import os

import pytest

@pytest.fixture
def test_song():
    title = 'Armin van Buuren - This Is A Test (Extended Mix)'
    url = 'https://www.youtube.com/watch?v=fIrrHUaXpAE'
    return Song(url, title)

@pytest.fixture
def test_user():
    user_id = '570087452245622800'
    user_name = 'jadedtdttest'
    return User(user_id, user_name)

@pytest.fixture
def vanilla_apl(test_sqlcon, test_song, test_user):
    return AutoPlaylist(None, [], [])

@pytest.mark.asyncio
async def test_precondition(vanilla_apl, test_song):
    results = await vanilla_apl.sqlfactory.song_read(test_song.url)
    if results:
        assert await vanilla_apl.sqlfactory.song_delete(test_song.url)

@pytest.mark.asyncio
async def test_user_like_song(vanilla_apl, test_song, test_user):
    # fresh slate
    await test_precondition(vanilla_apl, test_song)

    # liking a song that wasn't liked yet
    assert await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title)

    # liking a song the user already likes
    assert not await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title) 

@pytest.mark.asyncio
async def test_user_dislike_song(vanilla_apl, test_song, test_user):
    # fresh slate
    await test_precondition(vanilla_apl, test_song)

    # making user previously like the song
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    # disliking a song user liked
    assert await vanilla_apl.user_dislike_song(test_user.user_id, test_song.url, test_song.title)    

    # disliking a song that doesn't exist
    assert not await vanilla_apl.user_dislike_song(test_user.user_id, test_song.url, test_song.title)    
