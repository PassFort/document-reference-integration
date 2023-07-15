from copy import deepcopy
from datetime import datetime
from typing import List
from uuid import UUID

from flask import Blueprint, send_file, Response, abort

from app.api import Document, DatedAddress, DemoResultType, Error, ErrorType, Field, \
    DocumentData, RunCheckRequest, RunCheckResponse, validate_models, IndividualData, \
    DocumentResult, CheckedDocumentFieldResult, FinishResponse, \
    FinishRequest, DownloadFileRequest, DocumentCategory, DocumentType, DocumentImageType, DownloadType, FileType
from app.auth import auth
from app.shared import create_demo_field_checks, create_demo_forgery_check, create_demo_image_check, invalid_fields_from_result_type, run_demo_check, task_thread, uncertain_fields_from_result_type, blueprint as shared_blueprint

blueprint = Blueprint('doccapture', __name__, url_prefix='/doccapture')
blueprint.register_blueprint(shared_blueprint)

SUPPORTED_COUNTRIES = ['GBR', 'USA', 'CAN', 'NLD']
DEMO_PROVIDER_ID = UUID('DF5C42A0-0D56-4870-9362-33DE8DDDC08F')

def _proof_document(category: DocumentCategory) -> Document:
    """
    Initiates a document and populates it with inital data, with category assigning
    wheter this is an address or identity document
    """
    return Document({
        'category': category,
        'document_type': DocumentType.PASSPORT,
        'images': [{
            'image_type': DocumentImageType.FRONT,
            'upload_date': datetime.now(),
            'provider_reference': 'DUMMY_FILE'
        }],
        'files': [
            {
                'type': FileType.LIVE_VIDEO,
                'reference': 'DUMMY_FILE'
            },
            {
                'type': FileType.VIDEO_FRAME,
                'reference': 'DUMMY_FILE'
            }
        ]
    })


def _synthesize_demo_result(entity_data: IndividualData, demo_result: DemoResultType) -> List[Document]:
    """
    Populates a document with the extracted_data and verification_result
    based on the desired demo_result
    """
    # If we get an 'ANY' Demo Request, treat it as an ALL_PASS
    if demo_result == DemoResultType.ANY:
        demo_result = DemoResultType.DOCUMENT_ALL_CATEGORIES_ALL_PASS

    proof_of_address = _proof_document(DocumentCategory.PROOF_OF_ADDRESS)
    proof_of_identity = _proof_document(DocumentCategory.PROOF_OF_IDENTITY)

    # Extract only one address from the history
    current_address = entity_data.get_current_address()
    dated_address = [DatedAddress({'address': current_address})] if current_address else []

    all_passed_result = DocumentResult({
        'all_passed': True,
        'document_type_passed': True,
        'field_checks': [],
        'forgery_checks': [],
        'forgery_checks_passed': True,
        'image_checks': [],
        'image_checks_passed': True,
        'provider_name': "Document Capture Reference",
    })

    # Only generate field checks if the document would be valid
    field_checks = create_demo_field_checks(
        invalid_fields_from_result_type(demo_result),
        uncertain_fields_from_result_type(demo_result),
    )
    image_checks_passed = 'IMAGE_CHECK_FAILURE' not in demo_result
    forgery_checks_passed = 'FORGERY_CHECK_FAILURE' not in demo_result
    field_checks_passed = all(fc.result is CheckedDocumentFieldResult.CHECK_VALID for fc in field_checks)
    all_passed = image_checks_passed and forgery_checks_passed and field_checks_passed

    personal_details = entity_data.personal_details.to_primitive()

    result = DocumentResult({
        'all_passed': all_passed,
        'document_type_passed': True,
        'field_checks': field_checks,
        'forgery_checks': [create_demo_forgery_check(forgery_checks_passed)],
        'forgery_checks_passed': forgery_checks_passed,
        'image_checks': [create_demo_image_check(image_checks_passed)],
        'image_checks_passed': image_checks_passed,
        'provider_name': "Document Capture Reference",
    })

    happy_extracted = DocumentData({
        'address_history': dated_address,
        'personal_details': deepcopy(personal_details),
        'result': all_passed_result
    })
    sad_extracted = DocumentData({
        'address_history': dated_address,
        'personal_details': deepcopy(personal_details),
        'result': result
    })

    proof_of_address.extracted_data = happy_extracted
    proof_of_address.verification_result = all_passed_result

    proof_of_identity.extracted_data = happy_extracted
    proof_of_identity.verification_result = all_passed_result

    if 'CATEGORIES_ADDRESS' in demo_result or 'CATEGORY_ADDRESS' in demo_result:
        proof_of_address.verification_result = result
        proof_of_address.extracted_data = sad_extracted

        if 'NAME_FIELD_UNREADABLE' in demo_result:
            proof_of_address.extracted_data.personal_details.name = None

        if 'NAME_FIELD_DIFFERENT' in demo_result:
            proof_of_address.extracted_data.personal_details.name.family_name = "NOT-THE-ORIGINAL-FAMILY-NAME"

        if 'DOB_FIELD_UNREADABLE' in demo_result:
            proof_of_address.extracted_data.personal_details.dob = None

        if 'DOB_FIELD_DIFFERENT' in demo_result:
            dob = proof_of_address.extracted_data.personal_details.dob 
            if dob != "2000": 
                proof_of_address.extracted_data.personal_details.dob = 2000
            else:
                proof_of_address.extracted_data.personal_details.dob = 2001




    if 'CATEGORIES_IDENTITY' in demo_result or 'CATEGORY_IDENTITY' in demo_result:
        proof_of_identity.verification_result = result
        proof_of_identity.extracted_data = sad_extracted

        if 'NAME_FIELD_UNREADABLE' in demo_result:
            proof_of_identity.extracted_data.personal_details.name = None

        if 'NAME_FIELD_DIFFERENT' in demo_result:
            proof_of_identity.extracted_data.personal_details.name.family_name = "NOT-THE-ORIGINAL-FAMILY-NAME"

        if 'DOB_FIELD_UNREADABLE' in demo_result:
            proof_of_identity.extracted_data.personal_details.dob = None

        if 'DOB_FIELD_DIFFERENT' in demo_result:
            dob = proof_of_identity.extracted_data.personal_details.dob 
            if dob != "2000": 
                proof_of_identity.extracted_data.personal_details.dob = 2000
            else:
                proof_of_identity.extracted_data.personal_details.dob = 2001



    # Reference for which file to download based on the result
    if proof_of_address and proof_of_address.verification_result.all_passed:
        proof_of_address.images[0].provider_reference = 'DUMMY_FILE_ADDRESS_PASS'
        proof_of_address.files[0].reference = 'DUMMY_FILE_ADDRESS_PASS'
        proof_of_address.files[1].reference = 'DUMMY_FILE_ADDRESS_PASS'
    else:
        proof_of_address.images[0].provider_reference = 'DUMMY_FILE_ADDRESS_FAIL'
        proof_of_address.files[0].reference = 'DUMMY_FILE_ADDRESS_FAIL'
        proof_of_address.files[1].reference = 'DUMMY_FILE_ADDRESS_FAIL'

    if proof_of_identity and proof_of_identity.verification_result.all_passed:
        proof_of_identity.images[0].provider_reference = 'DUMMY_FILE_IDENTITY_PASS'
        proof_of_identity.files[0].reference = 'DUMMY_FILE_IDENTITY_PASS'
        proof_of_identity.files[1].reference = 'DUMMY_FILE_IDENTITY_PASS'
    else:
        proof_of_identity.images[0].provider_reference = 'DUMMY_FILE_IDENTITY_FAIL'
        proof_of_identity.files[0].reference = 'DUMMY_FILE_IDENTITY_FAIL'
        proof_of_identity.files[1].reference = 'DUMMY_FILE_IDENTITY_FAIL'



    if 'ALL_CATEGORIES' in demo_result:
        return [
            proof_of_address,
            proof_of_identity,
        ]

    if 'SINGLE_CATEGORY_ADDRESS' in demo_result:
        return [
            proof_of_address
        ]

    if 'SINGLE_CATEGORY_IDENTITY' in demo_result:
        return [
            proof_of_identity
        ]


@blueprint.route('/')
def index():
    return send_file('../static/doccapture/metadata.json', max_age=-1)


@blueprint.route('/config')
@auth.login_required
def get_config():
    return send_file('../static/doccapture/config.json', max_age=-1)

@blueprint.route('/checks', methods=['POST'])
@validate_models
def run_check(req: RunCheckRequest) -> RunCheckResponse:
    return run_demo_check(DEMO_PROVIDER_ID, req.id, req.check_input, req.demo_result, _synthesize_demo_result)

    return RunCheckResponse.error(DEMO_PROVIDER_ID, [Error({
        'type': ErrorType.PROVIDER_MESSAGE,
        'message': 'Live checks are not supported',
    })])


@blueprint.route('/checks/<uuid:_id>/complete', methods=['POST'])
@validate_models
def complete_check(req: FinishRequest, _id: UUID) -> FinishResponse:
    # We probably shouldn't have made it this far if they were trying a live check
    if not req.reference.startswith('DEMODATA-'):
        return FinishResponse.error([Error({
            'type': ErrorType.PROVIDER_MESSAGE,
            'message': 'Live checks are not supported',
        })])

    if not req.custom_data:
        return FinishResponse.error([Error({
            'type': ErrorType.PROVIDER_MESSAGE,
            'message': 'Demo finish request did not contain demo result',
        })])

    resp = FinishResponse()
    resp.import_data(req.custom_data)
    return resp


