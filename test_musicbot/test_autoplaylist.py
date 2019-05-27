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
def test_other_user():
    user_id = '181268300301336576'
    user_name = 'Jadedtdt'
    return User(user_id, user_name)

@pytest.fixture
def vanilla_apl(test_song, test_user):
    return AutoPlaylist(None, [], [])

@pytest.mark.asyncio
async def test_precondition(vanilla_apl, test_song):
    results = await vanilla_apl.sqlfactory.song_read(test_song.url)
    if results:
        assert await vanilla_apl.sqlfactory.song_delete(test_song.url)

@pytest.mark.asyncio
async def test_UserLikeSong_NoPreviousSong(vanilla_apl, test_song, test_user):
    await test_precondition(vanilla_apl, test_song)

    assert await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserLikeSong_LikedByUser(vanilla_apl, test_song, test_user):
    await test_precondition(vanilla_apl, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)

    assert not await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserLikeSong_LikedByOther(vanilla_apl, test_song, test_user, test_other_user):
    await test_precondition(vanilla_apl, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_other_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserLikeSong_LikedByUserAndOther(vanilla_apl, test_song, test_user, test_other_user):
    await test_precondition(vanilla_apl, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_other_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert not await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserDislikeSong_NoPreviousSong(vanilla_apl, test_song, test_user):
    await test_precondition(vanilla_apl, test_song)
    
    assert not await vanilla_apl.user_dislike_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserDislikeSong_LikedByUser(vanilla_apl, test_song, test_user):
    await test_precondition(vanilla_apl, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert await vanilla_apl.user_dislike_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserDislikeSong_LikedByOther(vanilla_apl, test_song, test_user, test_other_user):
    await test_precondition(vanilla_apl, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_other_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert not await vanilla_apl.user_dislike_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserDislikeSong_LikedByUserAndOther(vanilla_apl, test_song, test_user, test_other_user):
    await test_precondition(vanilla_apl, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_other_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert await vanilla_apl.user_dislike_song(test_user.user_id, test_song.url, test_song.title)
