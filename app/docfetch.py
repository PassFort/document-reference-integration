from threading import Thread
from typing import Optional, List, Tuple
from uuid import UUID, uuid4
from flask import Blueprint, send_file, request, Response

from app.auth import auth
from app.startup import passfort_base_url
from app.api import Address, Document, DatedAddress, DecisionClass, DemoResultType, Error, ErrorType, Field, \
    FieldCheckResult, DocumentData, RunCheckRequest, RunCheckResponse, validate_models, IndividualData, \
    DocumentResult, CheckedDocumentFieldResult, CheckedDocumentField, DocumentCheck, FinishResponse, \
    FinishRequest, DownloadImageRequest

blueprint = Blueprint('docfetch', __name__, url_prefix='/docfetch')

SUPPORTED_COUNTRIES = ['GBR', 'USA', 'CAN', 'NLD']


@blueprint.route('/')
def index():
    return send_file('../static/docfetch/metadata.json', cache_timeout=-1)


@blueprint.route('/config')
@auth.login_required
def get_config():
    return send_file('../static/docfetch/config.json', cache_timeout=-1)


# Starts the check
@blueprint.route('/checks', methods=['POST'])
@auth.login_required
@validate_models
def run_check(req: RunCheckRequest) -> RunCheckResponse:
    raise NotImplementedError()


# Return the final response to a request from the server
@blueprint.route('/checks/<uuid:id>/complete', methods=['POST'])
@auth.login_required
@validate_models
def finish_check(req: FinishRequest, id: UUID) -> FinishResponse:
    raise NotImplementedError()


# Download an image
@blueprint.route('/download_image', methods=['POST'])
@auth.login_required
@validate_models
def download_image(req: DownloadImageRequest) -> Response:
    raise NotImplementedError()
