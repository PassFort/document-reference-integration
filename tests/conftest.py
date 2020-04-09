import logging
import sys
import warnings

import pytest

from requests_http_signature import HTTPSignatureAuth
from requests_flask_adapter import FlaskAdapter
from requests import Session

import tests.startup

sys.modules['app.startup'] = tests.startup


@pytest.fixture
def session():
    from main import app

    app.testing = True
    app.logger.setLevel(logging.INFO)

    with Session() as session:
        session.mount('http://app', FlaskAdapter(app))
        yield session


@pytest.fixture
def auth():
    return lambda key=tests.startup.dummy_key, headers=None: HTTPSignatureAuth(
        key=key,
        key_id='dummykey',
        headers=['(request-target)', 'date'] if headers is None else headers
    )
