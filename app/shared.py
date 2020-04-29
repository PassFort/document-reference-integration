from typing import List
from uuid import UUID
import requests

from app.auth import outbound_auth
from app.startup import passfort_base_url
from app.api import DecisionClass, DemoResultType, FieldCheckResult, \
    CheckedDocumentFieldResult, CheckedDocumentField, DocumentCheck


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
    if demo_result_type == DemoResultType.DOCUMENT_DOB_FIELD_UNREADABLE:
        return [CheckedDocumentField.FIELD_DOB]

    if demo_result_type == DemoResultType.DOCUMENT_NAME_FIELD_UNREADABLE:
        return [CheckedDocumentField.FIELD_FAMILY_NAME, CheckedDocumentField.FIELD_GIVEN_NAMES]

    return []


def invalid_fields_from_result_type(demo_result_type: DemoResultType) -> List[CheckedDocumentField]:
    if demo_result_type == DemoResultType.DOCUMENT_DOB_FIELD_DIFFERENT:
        return [CheckedDocumentField.FIELD_DOB]

    if demo_result_type == DemoResultType.DOCUMENT_NAME_FIELD_DIFFERENT:
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
