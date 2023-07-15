from threading import Thread
from typing import List
from uuid import UUID

import requests
from flask import Blueprint, Response, send_file, abort

from app.auth import auth, outbound_auth
from app.startup import passfort_base_url
from app.api import DecisionClass, DemoResultType, DownloadFileRequest, DownloadType, Error, FieldCheckResult, \
    CheckedDocumentFieldResult, CheckedDocumentField, DocumentCheck, FileType, IndividualData, RunCheckResponse, validate_models

blueprint = Blueprint("shared", __name__)

def create_demo_field_checks(
    invalid_fields: List[CheckedDocumentField],
    uncertain_fields: List[CheckedDocumentField],
) -> List[FieldCheckResult]:
    demo_fields = [
        CheckedDocumentField.FIELD_ADDRESS,
        CheckedDocumentField.FIELD_DOB,
        CheckedDocumentField.FIELD_FAMILY_NAME,
        CheckedDocumentField.FIELD_GIVEN_NAMES,
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


def uncertain_fields_from_result_type(demo_result_type: DemoResultType) -> List[CheckedDocumentField]:
    if 'DOB_FIELD_UNREADABLE' in demo_result_type:
        return [CheckedDocumentField.FIELD_DOB]

    if 'NAME_FIELD_UNREADABLE' in demo_result_type:
        return [CheckedDocumentField.FIELD_FAMILY_NAME, CheckedDocumentField.FIELD_GIVEN_NAMES]

    return []


def invalid_fields_from_result_type(demo_result_type: DemoResultType) -> List[CheckedDocumentField]:
    if 'DOB_FIELD_DIFFERENT' in demo_result_type:
        return [CheckedDocumentField.FIELD_DOB]

    if 'NAME_FIELD_DIFFERENT' in demo_result_type:
        return [CheckedDocumentField.FIELD_FAMILY_NAME, CheckedDocumentField.FIELD_GIVEN_NAMES]

    return []


def create_demo_forgery_check(passed: bool) -> DocumentCheck:
    result = DecisionClass.PASS if passed else DecisionClass.FAIL
    return DocumentCheck({
        'category': 'FORGERY_CHECK',
        'result': result,
        'type': 'IMAGE_TAMPERING',
    })


def create_demo_image_check(passed: bool) -> DocumentCheck:
    result = DecisionClass.PASS if passed else DecisionClass.FAIL
    return DocumentCheck({
        'category': 'IMAGE_CHECK',
        'result': result,
        'type': 'IMAGE_SHARPNESS',
    })


def _callback(provider_id: UUID, reference: str):
    session = requests.Session()
    url = f'{passfort_base_url}/v1/callbacks'

    session.post(url, json={
        'provider_id': str(provider_id),
        'reference': reference
    }, auth=outbound_auth())


# Do some work outside the request handler to simulate doing some work
# asynchronously through a provider
def task_thread(provider_id: UUID, reference: str):
    import time

    # Don't run too quickly, we need the sync request to complete first
    time.sleep(0.1)
    
    _callback(provider_id, reference)

# We store the computed demo result in the custom data retained for us
# by the server
def run_demo_check(provider_id: UUID, check_id: UUID, check_input: IndividualData, demo_result: str, synthesize_demo_result) -> RunCheckResponse:
    check_output = IndividualData({
        'documents': synthesize_demo_result(check_input, demo_result)
    })

    custom_data = {'errors': []}
    if demo_result == DemoResultType.ERROR_INVALID_CREDENTIALS:
        custom_data['errors'].append(Error.invalid_credentials('Invalid credentials demo').serialize())

    if demo_result == DemoResultType.ERROR_ANY_PROVIDER_MESSAGE:
        custom_data['errors'].append(Error.provider_message('Demo provider message').serialize())

    if demo_result == DemoResultType.ERROR_CONNECTION_TO_PROVIDER:
        custom_data['errors'].append(Error.provider_connection('Demo provider connection issue').serialize())

    if demo_result == DemoResultType.ERROR_MISSING_CONTACT_DETAILS:
        custom_data['errors'].append(Error.missing_contact_details().serialize())

    if demo_result not in DemoResultType.variants:
        custom_data['errors'].append(Error.unsupported_demo_result(demo_result).serialize())

    if len(custom_data['errors']) == 0:
        custom_data['check_output'] = check_output.serialize()

    response = RunCheckResponse({
        'provider_id': provider_id,
        'reference': f'DEMODATA-{check_id}',
        'custom_data': custom_data,
    })

    # Prepare a callback to be fired in another thread
    _cb = Thread(target=task_thread, args=(response['provider_id'], response['reference']))
    _cb.start()

    return response

# Download an image
@blueprint.route('/download_file', methods=['POST'])
@auth.login_required
@validate_models
def download_file(req: DownloadFileRequest) -> Response:
    # We probably shouldn't have made it this far if they were trying a live check
    if 'DUMMY_FILE' not in req.file_reference:
        abort(400, 'Live checks are not supported')

    # Video file
    if req.download_info.download_type == DownloadType.FILE and req.download_info.file_type == FileType.LIVE_VIDEO:
        return send_file('../static/docfetch/demo_video.mp4', max_age=-1)

    # Address files (and video thumbnail) - passed and failed
    elif (req.download_info.download_type == DownloadType.IMAGE or (req.download_info.download_type == DownloadType.FILE and req.download_info.file_type ==  FileType.VIDEO_FRAME)) and 'ADDRESS' in req.file_reference:
        if 'PASS' in req.file_reference:
            return send_file('../static/docfetch/demo_image_address_pass.png', max_age=-1)
        else:
            return send_file('../static/docfetch/demo_image_address_fail.png', max_age=-1)

    # Identity files (and video thumbnail) - passed and failed
    elif (req.download_info.download_type == DownloadType.IMAGE or (req.download_info.download_type == DownloadType.FILE and req.download_info.file_type ==  FileType.VIDEO_FRAME)) and 'IDENTITY' in req.file_reference:
        if 'PASS' in req.file_reference:
            return send_file('../static/docfetch/demo_image_identity_pass.png', max_age=-1)
        else:
            return send_file('../static/docfetch/demo_image_identity_fail.png', max_age=-1)

    # Fallback to generic image
    else:
        return send_file('../static/docfetch/demo_image.png', max_age=-1)
