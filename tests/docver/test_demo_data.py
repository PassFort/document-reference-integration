from app.api import CheckedDocumentField, CheckedDocumentFieldResult, Document, IndividualData, DemoResultType
from app.docver import _create_demo_field_checks, _synthesize_demo_result

def test_all_valid_demo_field_checks():
    checks = _create_demo_field_checks([], [])

    assert len(checks) == 4
    for c in checks:
        assert c.result == CheckedDocumentFieldResult.CHECK_VALID


def test_invalid_demo_field_checks():
    checks = _create_demo_field_checks([CheckedDocumentField.FIELD_DOB], [])

    assert len(checks) == 4
    for c in checks:
        if c.field is CheckedDocumentField.FIELD_DOB:
            assert c.result == CheckedDocumentFieldResult.CHECK_INVALID
        else:
            assert c.result == CheckedDocumentFieldResult.CHECK_VALID


def test_uncertain_demo_field_checks():
    checks = _create_demo_field_checks([], [CheckedDocumentField.FIELD_DOB])

    assert len(checks) == 4
    for c in checks:
        if c.field is CheckedDocumentField.FIELD_DOB:
            assert c.result == CheckedDocumentFieldResult.CHECK_UNCERTAIN
        else:
            assert c.result == CheckedDocumentFieldResult.CHECK_VALID


def _make_document():
    return Document({
        'category': 'PROOF_OF_IDENTITY',
        'document_type': 'BIOMETRIC_STATE_ID',
        'id': '899e952b-dccc-463c-b442-b0a31d5553d9',
        'images': []
    })


def _make_entity():
    return IndividualData({
        'entity_type': 'INDIVIDUAL',
        'personal_details': {
            'name': {
                'title': 'Mr',
                'given_names': ['John'],
                'family_name': 'Smith'
            },
            'dob': '1985-04-21',
        },
        'documents': []
    })


def test_passing_demo_result():
    document = _make_document()
    entity_data = _make_entity()

    result = _synthesize_demo_result(document, entity_data, DemoResultType.DOCUMENT_ALL_PASS)
    assert result.verification_result.all_passed
    assert len(result.verification_result.field_checks) == 4
    assert len(result.verification_result.forgery_checks) == 1
    assert len(result.verification_result.image_checks) == 1


def test_invalid_doc_demo_result():
    document = _make_document()
    entity_data = _make_entity()

    result = _synthesize_demo_result(document, entity_data, DemoResultType.ERROR_UNSUPPORTED_DOCUMENT_TYPE)
    assert not result.verification_result.all_passed
    assert not result.verification_result.document_type_passed
    assert result.verification_result.error_reason == 'Unsupported document type'


def test_forgery_demo_result():
    document = _make_document()
    entity_data = _make_entity()

    result = _synthesize_demo_result(document, entity_data, DemoResultType.DOCUMENT_FORGERY_CHECK_FAILURE)

    assert not result.verification_result.forgery_checks_passed


def test_image_quality_demo_result():
    document = _make_document()
    entity_data = _make_entity()

    result = _synthesize_demo_result(document, entity_data, DemoResultType.DOCUMENT_IMAGE_CHECK_FAILURE)

    assert not result.verification_result.image_checks_passed
