from autoplaylist import Autoplaylist
from sqlfactory import SqlFactory

@pytest.fixture
def vanilla_apl():
    return Autoplaylist()

def test_default_songs(vanilla_apl):
    assert vanilla_apl.songs == vanilla_apl._get_songs()

def test_default_users(vanilla_apl):
    assert vanilla_apl.users == vanilla_apl._get_users()

def test_default_sqlfactory(vanilla_apl):
    assert isinstance(vanilla_apl.sqlfactory, SqlFactory)