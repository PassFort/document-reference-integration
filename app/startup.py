# This file is mocked out for testing (see `tests/conftest.py`)

import base64
import os
import sys
import logging


def _env(name):
    try:
        return os.environ[name]
    except KeyError:
        sys.exit(f'Missing required environment variable: {name}')


_integration_secret_key = _env('INTEGRATION_SECRET_KEY')
callback_url = _env('PASSFORT_CALLBACK_URL')

integration_key_store = {
    _integration_secret_key[:8]: base64.b64decode(_integration_secret_key)
}
integration_key_id = _integration_secret_key[:8]

logging.basicConfig(level=os.environ.get('LOGLEVEL', 'INFO'))
