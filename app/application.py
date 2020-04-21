from dataclasses import dataclass
from typing import Optional, List, Tuple
import uuid
import threading

from dataclasses import dataclass
from flask import Flask, send_file, request
from requests_http_signature import HTTPSignatureAuth as OutboundSignatureAuth
import requests

from app.http_signature import HTTPSignatureAuth
from app.startup import integration_key_store, integration_key_id, callback_url
from app.api import Address, Document, DatedAddress, DecisionClass, DemoResultType, Error, ErrorType, Field, \
    FieldCheckResult, DocumentData, RunCheckRequest, RunCheckResponse, validate_models, IndividualData, \
    DocumentResult, CheckedDocumentFieldResult, CheckedDocumentField, DocumentCheck, FinishResponse, \
    FinishRequest

# If `entrypoint` is not defined in app.yaml, App Engine will look
# for an app called `app` in `main.py`
app = Flask(__name__)

auth = HTTPSignatureAuth()

SUPPORTED_COUNTRIES = ['GBR', 'USA', 'CAN', 'NLD']


@auth.resolve_key
def resolve_key(key_id):
    return integration_key_store.get(key_id)


def outbound_auth(headers=None):
    return OutboundSignatureAuth(
        key=resolve_key(integration_key_id),
        key_id=integration_key_id,
        headers=['(request-target)', 'date'] if headers is None else headers
    )


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


def _create_demo_field_checks(
    invalid_fields: List[CheckedDocumentField],
    uncertain_fields: List[CheckedDocumentField],
) -> List[FieldCheckResult]:
    demo_fields = [
        CheckedDocumentField.FIELD_ADDRESS,
        CheckedDocumentField.FIELD_DOB,
        CheckedDocumentField.FIELD_FAMILYNAME,
        CheckedDocumentField.FIELD_GIVENNAMES,
    ]

    valid = [
        FieldCheckResult({'field': f, 'result': CheckedDocumentFieldResult.CHECK_VALID})
        for f in demo_fields if f not in invalid_fields and f not in uncertain_fields
    ]

    invalid = [
        FieldCheckResult({'field': f, 'result': CheckedDocumentFieldResult.CHECK_INVALID})
        for f in demo_fields if f in invalid_fields
    ]

    uncertain = [
        FieldCheckResult({'field': f, 'result': CheckedDocumentFieldResult.CHECK_UNCERTAIN})
        for f in demo_fields if f in uncertain_fields
    ]

    return [*valid, *invalid, *uncertain]


def _uncertain_fields_from_result_type(demo_result_type: DemoResultType) -> List[CheckedDocumentField]:
    if demo_result_type == DemoResultType.DOCUMENT_DOB_FIELD_UNREADABLE:
        return [CheckedDocumentField.FIELD_DOB]

    if demo_result_type == DemoResultType.DOCUMENT_NAME_FIELD_UNREADABLE:
        return [CheckedDocumentField.FAMILYNAME, CheckedDocumentField.GIVENNAMES]

    return []


def _invalid_fields_from_result_type(demo_result_type: DemoResultType) -> List[CheckedDocumentField]:
    if demo_result_type == DemoResultType.DOCUMENT_DOB_FIELD_DIFFERENT:
        return [CheckedDocumentField.FIELD_DOB]

    if demo_result_type == DemoResultType.DOCUMENT_NAME_FIELD_DIFFERENT:
        return [CheckedDocumentField.FAMILYNAME, CheckedDocumentField.GIVENNAMES]

    return []


def _create_demo_forgery_check(passed: bool) -> DocumentCheck:
    result = DecisionClass.PASS if passed else DecisionClass.FAIL
    return DocumentCheck({
        'category': 'FORGERY_CHECK',
        'result': result,
        'type': 'IMAGE_TAMPERING',
    })


def _create_demo_image_check(passed: bool) -> DocumentCheck:
    result = DecisionClass.PASS if passed else DecisionClass.FAIL
    return DocumentCheck({
        'category': 'IMAGE_CHECK',
        'result': result,
        'type': 'IMAGE_SHARPNESS',
    })


"""
Takes a Document and populates the extracted_data and verification_result
based on the desired demo_result
"""
def _synthesize_demo_result(document: Document, entity_data: IndividualData, demo_result: DemoResultType) -> Document:
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
        field_checks = _create_demo_field_checks(
            _invalid_fields_from_result_type(demo_result),
            _uncertain_fields_from_result_type(demo_result),
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
        'forgery_checks': [_create_demo_forgery_check(forgery_checks_passed)],
        'forgery_checks_passed': forgery_checks_passed,
        'image_checks': [_create_demo_image_check(image_checks_passed)],
        'image_checks_passed': image_checks_passed,
        'provider_name': "Document Verification Reference",
    })

    extracted = DocumentData({
        'address_history': [dated_address],
        'personal_details': entity_data.personal_details,
        'result': result
    })

    document.extracted_data = extracted
    document.verification_result = result

    return document


def _extract_input(req: RunCheckRequest) -> Tuple[List[Error], Optional[IndividualData]]:
    errors = []

    # Extract address
    # TODO: Validate required address fields
    current_address = req.check_input.get_current_address()
    if current_address is None and req.provider_config.require_address:
        errors.append(Error.missing_required_field(Field.ADDRESS_HISTORY))

    # Extract DOB
    dob = req.check_input.get_dob()
    if dob is None and req.provider_config.require_dob:
        errors.append(Error.missing_required_field(Field.DOB))

    # Extract given names
    given_names = req.check_input.get_given_names()
    if given_names is None:
        errors.append(Error.missing_required_field(Field.GIVEN_NAMES))

    # Extract family name
    family_name = req.check_input.get_family_name()
    if family_name is None:
        errors.append(Error.missing_required_field(Field.FAMILY_NAME))

    # Extract documents
    documents = req.check_input.get_documents()
    if not documents:
        errors.append(Error.missing_documents())

    if errors:
        return errors, None
    else:
        return [], req.check_input


def _callback(provider_id: uuid.UUID, reference: str):
    session = requests.Session()
    url = f'{callback_url}/integrations/v1/callbacks'

    session.post(url, json={
        'provider_id': str(provider_id),
        'reference': reference
    }, auth=outbound_auth())


# Do some work outside the request handler to simulate doing some work
# asynchronously through a provider
def _task_thread(provider_id: uuid.UUID, reference: str, documents: List[uuid.UUID]):
    import time

    # Don't run too quickly, we need the sync request to complete first
    time.sleep(3)
    
    # TODO: Once the bridge supports document retrieval we should try and download
    # them before claiming to have completed the check.
    _callback(provider_id, reference)


# We store the computed demo result in the custom data retained for us
# by the server
def _run_demo_check(check_input: IndividualData, demo_result: str) -> RunCheckResponse:
    documents = check_input.get_documents()
    verified_documents = [
        _synthesize_demo_result(doc, check_input, demo_result)
        for doc in documents
    ]
    check_input.documents = verified_documents

    response = RunCheckResponse({
        'provider_id': str(uuid.uuid4()),
        'reference': 'DEMODATA',
        'custom_data': {
            'demo_result': check_input.to_primitive(),
        },
    })

    # Prepare a callback to be fired in another thread, which should attempt
    # to download the images and so on, before calling back into the server
    _cb = threading.Thread(target=_task_thread, args=(response['provider_id'], response['reference'], []))
    _cb.start()

    return response


# Starts the check
@app.route('/checks', methods=['POST'])
@auth.login_required
@validate_models
def run_check(req: RunCheckRequest) -> RunCheckResponse:
    errors, check_input = _extract_input(req)
    if errors:
        return RunCheckResponse.error(errors)

    country = check_input.get_current_address().country
    if country not in SUPPORTED_COUNTRIES:
        return RunCheckResponse.error([Error.unsupported_country()])

    if req.demo_result is not None:
        return _run_demo_check(check_input, req.demo_result)

    return RunCheckResponse.error([Error({
        'type': ErrorType.PROVIDER_MESSAGE,
        'message': 'Live checks are not supported',
    })])


# Return the final response to a request from the server
@app.route('/checks/<uuid:id>/complete', methods=['POST'])
@auth.login_required
@validate_models
def finish_check(req: FinishRequest, id: uuid.UUID) -> FinishResponse:
    # We probably shouldn't have made it this far if they were trying a live check
    if req.reference != 'DEMODATA':
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
        'check_output': req.custom_data['demo_result'],
    })

