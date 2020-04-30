from threading import Thread
from typing import List, Tuple
from uuid import UUID
from flask import Blueprint, send_file, Response, abort
from datetime import date

from app.auth import auth
from app.api import Document, DatedAddress, DemoResultType, Error, ErrorType, Field, \
    DocumentData, RunCheckRequest, RunCheckResponse, validate_models, IndividualData, \
    DocumentResult, CheckedDocumentFieldResult, FinishResponse, \
    FinishRequest, DownloadImageRequest, DocumentCategory, DocumentType, DocumentImageType
from app.shared import create_demo_field_checks, invalid_fields_from_result_type, uncertain_fields_from_result_type, \
    create_demo_forgery_check, create_demo_image_check, task_thread

blueprint = Blueprint('docfetch', __name__, url_prefix='/docfetch')

SUPPORTED_COUNTRIES = ['GBR', 'USA', 'CAN', 'NLD']
DEMO_PROVIDER_ID = UUID('5c0bf04f-fce5-4f3a-a078-33dab7f65783')


@blueprint.route('/')
def index():
    return send_file('../static/docfetch/metadata.json', cache_timeout=-1)


@blueprint.route('/config')
@auth.login_required
def get_config():
    return send_file('../static/docfetch/config.json', cache_timeout=-1)


def _extract_input(req: RunCheckRequest) -> Tuple[List[Error], str]:
    errors = []

    external_ref = req.check_input.get_external_ref()
    if external_ref is None:
        errors.append(Error.missing_required_field(Field.EXTERNAL_REFERENCE))

    if errors:
        return errors, None
    else:
        return [], external_ref


def _synthesize_demo_result(entity_data: IndividualData, demo_result: DemoResultType) -> Document:
    """
    Populates a document with the extracted_data and verification_result
    based on the desired demo_result
    """
    document = Document({
        'category': DocumentCategory.PROOF_OF_IDENTITY,
        'document_type': DocumentType.PASSPORT,
        'images': [{
            'image_type': DocumentImageType.FRONT,
            'upload_date': date.today(),
            'provider_reference': 'DUMMY_IMAGE'
        }]
    })

    # If we get an 'ANY' Demo Request, treat it as an ALL_PASS
    if demo_result == DemoResultType.ANY:
        demo_result = DemoResultType.DOCUMENT_ALL_PASS

    # For unsupported documents, bail out immediately
    if demo_result == DemoResultType.ERROR_UNSUPPORTED_DOCUMENT_TYPE:
        result = DocumentResult({
            'all_passed': False,
            'document_type_passed': False,
            'error_reason': 'Unsupported document type',
            'image_checks_passed': False,
            'provider_name': 'Document Verification Reference',
        })

        document.verification_result = result
        return document

    # Extract only one address from the history
    current_address = entity_data.get_current_address()
    dated_address = DatedAddress({'address': current_address})

    # Only generate field checks if the document would be valid
    field_checks = []
    if demo_result not in [DemoResultType.DOCUMENT_FORGERY_CHECK_FAILURE, DemoResultType.DOCUMENT_IMAGE_CHECK_FAILURE]:
        field_checks = create_demo_field_checks(
            invalid_fields_from_result_type(demo_result),
            uncertain_fields_from_result_type(demo_result),
        )

    image_checks_passed = demo_result is not DemoResultType.DOCUMENT_IMAGE_CHECK_FAILURE
    forgery_checks_passed = demo_result is not DemoResultType.DOCUMENT_FORGERY_CHECK_FAILURE
    field_checks_passed = True
    for fc in field_checks:
        if fc.result is not CheckedDocumentFieldResult.CHECK_VALID:
            field_checks_passed = False

    all_passed = image_checks_passed and forgery_checks_passed and field_checks_passed

    result = DocumentResult({
        'all_passed': all_passed,
        'document_type_passed': True,
        'field_checks': field_checks,
        'forgery_checks': [create_demo_forgery_check(forgery_checks_passed)],
        'forgery_checks_passed': forgery_checks_passed,
        'image_checks': [create_demo_image_check(image_checks_passed)],
        'image_checks_passed': image_checks_passed,
        'provider_name': "Document Fetch Reference",
    })

    extracted = DocumentData({
        'address_history': [dated_address],
        'personal_details': entity_data.personal_details,
        'result': result
    })

    document.extracted_data = extracted
    document.verification_result = result

    return document


# We store the computed demo result in the custom data retained for us
# by the server
def _run_demo_check(check_id: UUID, check_input: IndividualData, demo_result: str) -> RunCheckResponse:
    check_output = IndividualData({
        'documents': [
            _synthesize_demo_result(check_input, demo_result)
        ]
    })

    response = RunCheckResponse({
        'provider_id': DEMO_PROVIDER_ID,
        'reference': f'DEMODATA-{check_id}',
        'custom_data': {
            'demo_result': check_output.serialize(),
        },
    })

    # Prepare a callback to be fired in another thread
    _cb = Thread(target=task_thread, args=(response['provider_id'], response['reference']))
    _cb.start()

    return response


# Starts the check
@blueprint.route('/checks', methods=['POST'])
@auth.login_required
@validate_models
def run_check(req: RunCheckRequest) -> RunCheckResponse:
    errors, _external_ref = _extract_input(req)
    if errors:
        return RunCheckResponse.error(errors)

    country = req.check_input.get_current_address().country
    if country not in SUPPORTED_COUNTRIES:
        return RunCheckResponse.error([Error.unsupported_country()])

    if req.demo_result is not None:
        return _run_demo_check(req.id, req.check_input, req.demo_result)

    return RunCheckResponse.error([Error({
        'type': ErrorType.PROVIDER_MESSAGE,
        'message': 'Live checks are not supported',
    })])


# Return the final response to a request from the server
@blueprint.route('/checks/<uuid:_id>/complete', methods=['POST'])
@auth.login_required
@validate_models
def finish_check(req: FinishRequest, _id: UUID) -> FinishResponse:
    # We probably shouldn't have made it this far if they were trying a live check
    if not req.reference.startswith('DEMODATA-'):
        return RunCheckResponse.error([Error({
            'type': ErrorType.PROVIDER_MESSAGE,
            'message': 'Live checks are not supported',
        })])

    if not req.custom_data or not req.custom_data.get('demo_result'):
        return RunCheckResponse.error([Error({
            'type': ErrorType.PROVIDER_MESSAGE,
            'message': 'Demo finish request did not contain demo result',
        })])


    return FinishResponse({
        'check_output': IndividualData().import_data(req.custom_data['demo_result']),
    })


# Download an image
@blueprint.route('/download_image', methods=['POST'])
@auth.login_required
@validate_models
def download_image(req: DownloadImageRequest) -> Response:
    # We probably shouldn't have made it this far if they were trying a live check
    if req.image_reference != 'DUMMY_IMAGE':
        abort(400, 'Live checks are not supported')
    
    return send_file('../static/docfetch/demo_image.png', cache_timeout=-1)
