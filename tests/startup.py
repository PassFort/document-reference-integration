import base64

dummy_key = base64.b64decode('dummykey') + bytes(250)

integration_key_store = {
    'dummykey': dummy_key
}
