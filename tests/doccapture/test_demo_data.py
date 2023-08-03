from app.api import IndividualData, DemoResultType
from app.doccapture import _synthesize_demo_result

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
    entity_data = _make_entity()
    result = _synthesize_demo_result(entity_data, DemoResultType.DOCUMENT_ALL_CATEGORIES_ALL_PASS)

    for document in result:
        if document.category == 'PROOF_OF_ADDRESS':
            address_result = document
        elif document.category == 'PROOF_OF_IDENTITY':
            identity_result = document

    assert address_result.verification_result.all_passed
    assert identity_result.verification_result.all_passed

def test_dob_field_unreadable_demo_result():
    entity_data = _make_entity()
    result = _synthesize_demo_result(entity_data, DemoResultType.DOCUMENT_ALL_CATEGORIES_ADDRESS_DOB_FIELD_UNREADABLE)
    
    for document in result:
        if document.category == 'PROOF_OF_ADDRESS':
            address_result = document
        elif document.category == 'PROOF_OF_IDENTITY':
            identity_result = document

    assert identity_result.verification_result.all_passed
    assert not address_result.verification_result.all_passed

    for field_check in address_result.verification_result.field_checks:
        if field_check.field == 'FIELD_DOB':
            dob_field_check = field_check

    assert dob_field_check.result == 'CHECK_UNCERTAIN'