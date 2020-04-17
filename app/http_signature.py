import base64
import hashlib
import hmac
import logging
import time
import calendar

from flask import request
from flask_httpauth import HTTPAuth
from email.utils import parsedate


class HTTPSignatureAuth(HTTPAuth):
    def __init__(self, scheme='Signature', realm=None, required_headers=None, require_digest=True):
        super().__init__(scheme, realm)

        if required_headers is None:
            required_headers = ['(request-target)', 'date']

        self.required_headers = required_headers
        self.require_digest = require_digest
        self.key_resolver = None

    def resolve_key(self, f):
        self.key_resolver = f
        return f

    @staticmethod
    def _decode_signature(signature):
        # TODO: Use a proper parser and handle escapes, commas, etc. between quotes
        return {i.split("=", 1)[0]: i.split("=", 1)[1].strip('"') for i in signature.split(",")}

    @staticmethod
    def _get_bytes_to_sign(headers):
        result = []
        for header in headers:
            if header == '(request-target)':
                path_url = request.full_path if request.query_string else request.path
                result.append(f'(request-target): {request.method.lower()} {path_url}')
            else:
                if header == 'host':
                    value = request.headers.get('host', request.host)
                else:
                    value = request.headers[header]
                result.append(f'{header}: {value}')
        return '\n'.join(result).encode()

    def authenticate(self, auth, _pw):
        # Get the current time as early as possible, this time is in UTC
        authentication_time = time.time()

        if auth is None:
            logging.warning('No authentication provided.')
            return False

        assert self.key_resolver is not None, 'Key resolver should be set before authenticating request.'

        sig_dict = self._decode_signature(auth['token'])
        for field in 'keyId', 'algorithm', 'signature':
            if field not in sig_dict:
                logging.warning('Malformed authorisation header.')
                return False

        if sig_dict['algorithm'] not in {'hmac-sha256', 'hs2019'}:
            logging.warning(f'Unsupported signature algorithm: {sig_dict["algorithm"]}')
            return False

        # We deviate from the spec here, which says the default should be '(created)'. However, this is only valid
        # for asymmetric signatures, which we don't support.
        headers = [header.lower() for header in sig_dict.get('headers', 'date').split(' ')]

        for header in self.required_headers:
            if header not in headers:
                logging.warning(f'Missing required header `{header}` in signature.')
                return False

        if self.require_digest and request.data:
            if 'digest' not in headers:
                logging.warning('Missing required header `digest` in signature.')
                return False

            encoded_digest = base64.b64encode(hashlib.sha256(request.data).digest()).decode()

            expected_digest = request.headers['digest']
            computed_digest = f'SHA-256={encoded_digest}'
            if expected_digest != computed_digest:
                logging.warning(f'Digest header does not match request body.\n'
                                f'    Expected: {expected_digest}\n'
                                f'    Computed: {computed_digest}')
                return False

        if 'date' in headers:
            # The struct_time returned by parsedate will be converted to epoch
            # time using the system TZ, so we must use calendar.timegm() to ensure
            # it's consistently UTC
            supplied_date = calendar.timegm(parsedate(request.headers['date']))

            # Require supplied date to be close to the current time
            if abs(authentication_time - supplied_date) > 30:
                logging.warning('Date on request too far away from current time.')
                return False

        expected_signature = base64.b64decode(sig_dict['signature'])

        bytes_to_sign = self._get_bytes_to_sign(headers)
        key = self.key_resolver(key_id=sig_dict['keyId'])
        if key is None:
            logging.warning(f'Unknown key ID `{sig_dict["keyId"]}` when verifying signature.')
            return False

        computed_signature = hmac.new(key, bytes_to_sign, digestmod=hashlib.sha256).digest()

        signature_valid = hmac.compare_digest(expected_signature, computed_signature)
        if not signature_valid:
            logging.warning(f'Signature on request does not match expected signature.')
        return signature_valid
