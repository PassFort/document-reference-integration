def test_metadata(session):
    r = session.get('http://app/')
    assert r.status_code == 200
    assert r.headers['content-type'] == 'application/json'

    res = r.json()
    assert res['protocol_version'] == 1
    assert isinstance(res['provider_name'], str)
