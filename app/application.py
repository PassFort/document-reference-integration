
from flask import Flask, request
import requests

from app.docver import blueprint as docver_blueprint
from app.docfetch import blueprint as docfetch_blueprint

# If `entrypoint` is not defined in app.yaml, App Engine will look
# for an app called `app` in `main.py`
app = Flask(__name__)


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

app.register_blueprint(docver_blueprint)
app.register_blueprint(docfetch_blueprint)
