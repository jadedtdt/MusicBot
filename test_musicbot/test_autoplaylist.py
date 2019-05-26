from musicbot.autoplaylist import AutoPlaylist
from musicbot.sqlfactory import SqlFactory

import pytest

@pytest.fixture
def vanilla_apl():
    return AutoPlaylist()

def test_default_songs(vanilla_apl):
    assert str(vanilla_apl.songs) == str(vanilla_apl._get_songs())

def test_default_users(vanilla_apl):
    assert str(vanilla_apl.users) == str(vanilla_apl._get_users())

def test_default_sqlfactory(vanilla_apl):
    assert isinstance(vanilla_apl.sqlfactory, SqlFactory)