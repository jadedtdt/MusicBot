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
async def test_Precondition_LikeDislike(vanilla_apl, test_user, test_song):
    results = await vanilla_apl.sqlfactory.song_read(test_song.url)
    if results:
        assert await vanilla_apl.sqlfactory.song_delete(test_song.url)
        
    results = await vanilla_apl.sqlfactory.user_song_read(test_user.user_id, test_song.url)
    if results:
        assert await vanilla_apl.sqlfactory.user_song_delete(test_user.user_id, test_song.url)

@pytest.mark.asyncio
async def test_Precondition_User(vanilla_apl, test_user):
    results = await vanilla_apl.sqlfactory.user_read(test_user.user_id)
    if results:
        assert await vanilla_apl.sqlfactory.user_delete(test_user.user_id)

@pytest.mark.asyncio
async def test_UserLikeSong_NoPreviousSong(vanilla_apl, test_user, test_song):
    await test_Precondition_User(vanilla_apl, test_user)
    assert await vanilla_apl.sqlfactory.user_create(test_user.user_id, test_user.user_name, test_user.mood, test_user.yti_url, test_user.updt_dt_tm, test_user.cret_dt_tm)
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_song)

    assert await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserLikeSong_LikedByUser(vanilla_apl, test_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)

    assert not await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserLikeSong_LikedByOther(vanilla_apl, test_user, test_other_user, test_song ):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_other_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserLikeSong_LikedByUserAndOther(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_other_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert not await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserDislikeSong_NoPreviousSong(vanilla_apl, test_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_song)
    
    assert not await vanilla_apl.user_dislike_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserDislikeSong_LikedByUser(vanilla_apl, test_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert await vanilla_apl.user_dislike_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserDislikeSong_LikedByOther(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_other_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert not await vanilla_apl.user_dislike_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserDislikeSong_LikedByUserAndOther(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_other_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert await vanilla_apl.user_dislike_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_AreSongsAvailable_SongsAvailable(vanilla_apl, test_user, test_other_user, test_song):
    assert await vanilla_apl.are_songs_available()

@pytest.mark.asyncio
async def test_GetUser_UserExists(vanilla_apl, test_user):
    await test_Precondition_User(vanilla_apl, test_user)
    assert await vanilla_apl.sqlfactory.user_create(test_user.user_id, test_user.user_name, test_user.mood, test_user.yti_url, test_user.updt_dt_tm, test_user.cret_dt_tm)

    found_user = await vanilla_apl.get_user(test_user.user_id)
    assert found_user is not None
    assert found_user.user_id == test_user.user_id and found_user.user_name == test_user.user_name

@pytest.mark.asyncio
async def test_GetUser_UserNotExists(vanilla_apl, test_user):
    await test_Precondition_User(vanilla_apl, test_user)

    found_user = await vanilla_apl.get_user(test_user.user_id)
    assert found_user is None

@pytest.mark.asyncio
async def test_FindSongByUrl_SongNotExistsAndUserSongNotExists(vanilla_apl, test_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_song)

    found_song = await vanilla_apl.find_song_by_url(test_song.url)
    assert found_song is None

@pytest.mark.asyncio
async def test_FindSongByUrl_SongExistsAndUserSongNotExists(vanilla_apl, test_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)

    found_song = await vanilla_apl.find_song_by_url(test_song.url)
    assert found_song is not None
    assert found_song.url == test_song.url and found_song.title == test_song.title

@pytest.mark.asyncio
async def test_FindSongByUrl_SongNotExistsAndUserSongExists(vanilla_apl, test_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_song)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)

    found_song = await vanilla_apl.find_song_by_url(test_song.url)
    assert found_song is None

@pytest.mark.asyncio
async def test_FindSongByUrl_SongExistsAndUserSongExists(vanilla_apl, test_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)

    found_song = await vanilla_apl.find_song_by_url(test_song.url)
    assert found_song is not None
    assert found_song.url == test_song.url and found_song.title == test_song.title

