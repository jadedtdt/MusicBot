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
async def test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song):
    results = await vanilla_apl.sqlfactory.song_read(test_song.url)
    if results:
        assert await vanilla_apl.sqlfactory.song_delete(test_song.url)
        
    results = await vanilla_apl.sqlfactory.user_song_read(test_user.user_id, test_song.url)
    if results:
        assert await vanilla_apl.sqlfactory.user_song_delete(test_user.user_id, test_song.url)
        
    results = await vanilla_apl.sqlfactory.user_song_read(test_other_user.user_id, test_song.url)
    if results:
        assert await vanilla_apl.sqlfactory.user_song_delete(test_other_user.user_id, test_song.url)

@pytest.mark.asyncio
async def test_Precondition_User(vanilla_apl, test_user):
    results = await vanilla_apl.sqlfactory.user_read(test_user.user_id)
    if results:
        assert await vanilla_apl.sqlfactory.user_delete(test_user.user_id)

@pytest.mark.asyncio
async def test_UserLikeSong_NoPreviousSong(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_User(vanilla_apl, test_user)
    assert await vanilla_apl.sqlfactory.user_create(test_user.user_id, test_user.user_name, test_user.mood, test_user.yti_url, test_user.updt_dt_tm, test_user.cret_dt_tm)
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)

    assert await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserLikeSong_LikedByUser(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)

    assert not await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserLikeSong_LikedByOther(vanilla_apl, test_user, test_other_user, test_song ):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_other_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserLikeSong_LikedByUserAndOther(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_other_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert not await vanilla_apl.user_like_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserDislikeSong_NoPreviousSong(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    
    assert not await vanilla_apl.user_dislike_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserDislikeSong_LikedByUser(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert await vanilla_apl.user_dislike_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserDislikeSong_LikedByOther(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_other_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    
    assert not await vanilla_apl.user_dislike_song(test_user.user_id, test_song.url, test_song.title)

@pytest.mark.asyncio
async def test_UserDislikeSong_LikedByUserAndOther(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
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
async def test_FindSongByUrl_SongNotExistsAndUserSongNotExists(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)

    found_song = await vanilla_apl.find_song_by_url(test_song.url)
    assert found_song is None

@pytest.mark.asyncio
async def test_FindSongByUrl_SongExistsAndUserSongNotExists(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)

    found_song = await vanilla_apl.find_song_by_url(test_song.url)
    assert found_song is not None
    assert found_song.url == test_song.url and found_song.title == test_song.title

@pytest.mark.asyncio
async def test_FindSongByUrl_SongNotExistsAndUserSongExists(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)

    found_song = await vanilla_apl.find_song_by_url(test_song.url)
    assert found_song is None

@pytest.mark.asyncio
async def test_FindSongByUrl_SongExistsAndUserSongExists(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)

    found_song = await vanilla_apl.find_song_by_url(test_song.url)
    assert found_song is not None
    assert found_song.url == test_song.url and found_song.title == test_song.title

@pytest.mark.asyncio
async def test_FindSongsByTitle_PercentInTitle(vanilla_apl, test_user, test_other_user, test_song):
    new_title = 'Song With % In It'
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, new_title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)

    found_songs = await vanilla_apl.find_songs_by_title(new_title)
    assert found_songs is not None and len(found_songs) == 0

@pytest.mark.asyncio
async def test_FindSongsByTitle_NoMatch(vanilla_apl, test_user, test_other_user, test_song):
    new_title = 'Song Title That Shouldnt Be Found'
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)

    found_songs = await vanilla_apl.find_songs_by_title(new_title)
    assert found_songs is not None and len(found_songs) == 0

@pytest.mark.asyncio
async def test_FindSongsByTitle_Match(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)

    found_songs = await vanilla_apl.find_songs_by_title(test_song.title)
    assert found_songs is not None and len(found_songs) > 0
    found = False
    for each_song in found_songs:
        if each_song.title == test_song.url:
            found = True
    assert found == True

@pytest.mark.asyncio
async def test_GetLikers_NoLikers(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_User(vanilla_apl, test_user)
    assert await vanilla_apl.sqlfactory.user_create(test_user.user_id, test_user.user_name, test_user.mood, test_user.yti_url, test_user.updt_dt_tm, test_user.cret_dt_tm)
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)

    found_likers = await vanilla_apl.get_likers(test_song.url)
    assert found_likers is not None and len(found_likers) == 0

@pytest.mark.asyncio
async def test_GetLikers_HasLikers(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_User(vanilla_apl, test_user)
    assert await vanilla_apl.sqlfactory.user_create(test_user.user_id, test_user.user_name, test_user.mood, test_user.yti_url, test_user.updt_dt_tm, test_user.cret_dt_tm)
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_other_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)

    found_likers = await vanilla_apl.get_likers(test_song.url)
    assert found_likers is not None and len(found_likers) > 0
    found = False
    for each_liker in found_likers:
        if each_liker.user_id == test_user.user_id and each_liker.user_name == test_user.user_name:
            found = True
        print('len: ' + str(len(found_likers)))
        print('each_liker info: user_id[{}], user_name[{}]'.format(each_liker.user_id, each_liker.user_name))
        print('test_user info: user_id[{}], user_name[{}]'.format(test_user.user_id, test_user.user_name))
    assert found == True

@pytest.mark.asyncio
async def test_GetSongs_HasSongsAndNotNewSong(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)

    found_songs = await vanilla_apl.get_songs()
    assert found_songs is not None and len(found_songs) > 0
    found = False
    for each_song in found_songs:
        if each_song.url == test_song.url and each_song.title == test_song.title:
            found = True
    assert found == False

@pytest.mark.asyncio
async def test_GetSongs_HasSongsAndNewSong(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)
    assert await vanilla_apl.sqlfactory.song_create(test_song.url, test_song.title, test_song.play_count, test_song.volume, test_song.updt_dt_tm, test_song.cret_dt_tm)
    assert await vanilla_apl.sqlfactory.user_song_create(test_user.user_id, test_song.url, test_song.play_count, test_song.updt_dt_tm)

    found_songs = await vanilla_apl.get_songs()
    assert found_songs is not None and len(found_songs) > 0
    found = False
    for each_song in found_songs:
        if each_song.url == test_song.url and each_song.title == test_song.title:
            found = True
    assert found == True

@pytest.mark.asyncio
async def test_GetUsers_HasUserAndNotNewUser(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_User(vanilla_apl, test_user)

    found_users = await vanilla_apl.get_users()
    assert found_users is not None and len(found_users) > 0
    found = False
    for each_user in found_users:
        if each_user.user_id == test_user.user_id and each_user.user_name == test_user.user_name:
            found = True
    assert found == False

@pytest.mark.asyncio
async def test_GetUsers_HasUserAndNewUser(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_User(vanilla_apl, test_user)
    assert await vanilla_apl.sqlfactory.user_create(test_user.user_id, test_user.user_name, test_user.mood, test_user.yti_url, test_user.updt_dt_tm, test_user.cret_dt_tm)

    found_users = await vanilla_apl.get_users()
    assert found_users is not None and len(found_users) > 0
    found = False
    for each_user in found_users:
        if each_user.user_id == test_user.user_id and each_user.user_name == test_user.user_name:
            found = True
    assert found == True

@pytest.mark.asyncio
async def test_Postcondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song):
    await test_Precondition_LikeDislike(vanilla_apl, test_user, test_other_user, test_song)

@pytest.mark.asyncio
async def test_Postcondition_User(vanilla_apl, test_user, test_song):
    await test_Precondition_User(vanilla_apl, test_user)