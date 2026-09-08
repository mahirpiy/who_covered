import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'


def load(name):
    """Loads a recorded ESPN payload."""

    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def scoreboard():
    return load('cfb_scoreboard.json')


@pytest.fixture
def push_scoreboard():
    return load('cfb_push_scoreboard.json')


@pytest.fixture
def odds_for():
    def _odds(event_id):
        return load(f'odds_{event_id}.json')

    return _odds


@pytest.fixture
def connection(tmp_path):
    import store

    conn = store.connect(str(tmp_path / 'test.db'))
    yield conn
    conn.close()
