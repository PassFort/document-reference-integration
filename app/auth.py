from requests_http_signature import HTTPSignatureAuth as OutboundSignatureAuth

from app.http_signature import HTTPSignatureAuth
from app.startup import integration_key_store, integration_key_id

auth = HTTPSignatureAuth()

@auth.resolve_key
def resolve_key(key_id):
    return integration_key_store.get(key_id)


def outbound_auth(headers=None):
    return OutboundSignatureAuth(
        key=resolve_key(integration_key_id),
        key_id=integration_key_id,
        headers=['(request-target)', 'date'] if headers is None else headers
    )
