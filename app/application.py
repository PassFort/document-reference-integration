from flask import Flask, send_file, request

from app.http_signature import HTTPSignatureAuth
from app.startup import integration_key_store

# If `entrypoint` is not defined in app.yaml, App Engine will look
# for an app called `app` in `main.py`
app = Flask(__name__)

auth = HTTPSignatureAuth()

@auth.resolve_key
def resolve_key(key_id, algorithm):
    return integration_key_store.get((key_id, algorithm))


@app.before_request
def pre_request_logging():
    request_data = '\n' + request.data.decode('utf8')
    request_data = request_data.replace('\n', '\n    ')

    app.logger.info(f'{request.method} {request.url}{request_data}')


@app.after_request
def post_request_logging(response):
    if response.direct_passthrough:
        response_data = '\n(direct pass-through)'
    else:
        response_data = '\n' + response.data.decode('utf8')
    response_data = response_data.replace('\n', '\n    ')

    app.logger.info(f'{response.status} {request.url}{response_data}')
    return response


@app.route('/')
def index():
    return send_file('../static/metadata.json', cache_timeout=-1)


@app.route('/config')
@auth.login_required
def get_config():
    return send_file('../static/config.json', cache_timeout=-1)
