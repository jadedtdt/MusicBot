<<<<<<< HEAD
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
=======
from autoplaylist import Autoplaylist
from sqlfactory import SqlFactory

@pytest.fixture
def vanilla_apl():
    return Autoplaylist()

def test_default_songs(vanilla_apl):
    assert vanilla_apl.songs == vanilla_apl._get_songs()

def test_default_users(vanilla_apl):
    assert vanilla_apl.users == vanilla_apl._get_users()
>>>>>>> 32a94346d86f1aa74f49a3cb13a577b0308f6956

def test_default_sqlfactory(vanilla_apl):
    assert isinstance(vanilla_apl.sqlfactory, SqlFactory)