import os
import time

from email.utils import formatdate


def test_config_protected(session, auth):
    # Should require authentication
    r = session.get('http://app/config')
    assert r.status_code == 401

    # Should require correct key
    bad_key = os.urandom(256)
    r = session.get('http://app/config', auth=auth(key=bad_key))
    assert r.status_code == 401

    # Should require '(request-target)' *and* 'date' headers to be signed
    r = session.get('http://app/config', auth=auth(headers=['date']))
    assert r.status_code == 401

    # Should require 'date' header to be recent
    old_date = formatdate(time.time() - 120)
    r = session.get('http://app/config', headers={'date': old_date}, auth=auth())
    assert r.status_code == 401


def test_config_smoke(session, auth):
    r = session.get('http://app/config', auth=auth())
    assert r.status_code == 200
    assert r.headers['content-type'] == 'application/json'

    res = r.json()

    assert 'check_type' in res
    assert 'check_template' in res

