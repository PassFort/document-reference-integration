from uuid import uuid4
from unittest.mock import patch

@patch('app.docfetch.task_thread')
def test_run_check_smoke(cbmock, session, auth):
    # Start the check
    r = session.post('http://app/docfetch/checks', json={
        'id': str(uuid4()),
        'check_input': {
            'entity_type': 'INDIVIDUAL',
            'personal_details': {
                'name': {
                    'given_names': ['Henry'],
                    'family_name': 'Gnarglefoot'
                },
                'dob': '1990-01-01'
            },
            'address_history': [
                {
                    'address': {
                        'country': 'GBR'
                    }
                }
            ],
            'external_refs': {
                "generic": "foobar"
            }
        },
        'commercial_relationship': 'DIRECT',
        'provider_config': {
            'require_dob': False,
            'require_address': False,
        },
        'demo_result': 'DOCUMENT_ALL_PASS'
    }, auth=auth())
    assert r.status_code == 200
    assert r.headers['content-type'] == 'application/json'

    res = r.json()

    assert res['errors'] == []
    assert cbmock.called

@patch('app.docfetch.task_thread')
def test_retrieve_demo_from_finish_endpoint(cbmock, session, auth):
    check_id = str(uuid4())
    provider_config = {
        'require_dob': False,
        'require_address': False,
    }
    # Start the check
    initial_request = session.post('http://app/docfetch/checks', json={
        'id': check_id,
        'check_input': {
            'entity_type': 'INDIVIDUAL',
            'personal_details': {
                'name': {
                    'given_names': ['Henry'],
                    'family_name': 'Gnarglefoot'
                },
                'dob': '1990-01-01'
            },
            'address_history': [
                {
                    'address': {
                        'country': 'GBR'
                    }
                }
            ],
            'external_refs': {
                "generic": "foobar2"
            }
        },
        'commercial_relationship': 'DIRECT',
        'provider_config': provider_config,
        'demo_result': 'DOCUMENT_ALL_PASS'
    }, auth=auth())
    assert initial_request.status_code == 200
    assert initial_request.headers['content-type'] == 'application/json'
    assert cbmock.called

    initial_result = initial_request.json()
    provider_id = initial_result['provider_id']
    reference = initial_result['reference']

    # Complete the check
    complete_request = session.post(f'http://app/docfetch/checks/{check_id}/complete', json={
        'id': check_id,
        'provider_id': provider_id,
        'reference': reference,
        'commercial_relationship': 'DIRECT',
        'provider_config': provider_config,
        'custom_data': initial_result['custom_data']
    }, auth=auth())
    assert complete_request.status_code == 200
    assert complete_request.headers['content-type'] == 'application/json'
    
    complete_result = complete_request.json()

    assert len(complete_result['check_output']['documents']) == 1
    assert complete_result['check_output']['documents'][0]['verification_result']['all_passed']

@patch('app.docfetch.task_thread')
def test_download_image(cbmock, session, auth):
    check_id = str(uuid4())
    provider_config = {
        'require_dob': False,
        'require_address': False,
    }
    # Start the check
    initial_request = session.post('http://app/docfetch/checks', json={
        'id': check_id,
        'check_input': {
            'entity_type': 'INDIVIDUAL',
            'personal_details': {
                'name': {
                    'given_names': ['Henry'],
                    'family_name': 'Gnarglefoot'
                },
                'dob': '1990-01-01'
            },
            'address_history': [
                {
                    'address': {
                        'country': 'GBR'
                    }
                }
            ],
            'external_refs': {
                "generic": "foobar2"
            }
        },
        'commercial_relationship': 'DIRECT',
        'provider_config': provider_config,
        'demo_result': 'DOCUMENT_ALL_PASS'
    }, auth=auth())
    assert initial_request.status_code == 200
    assert initial_request.headers['content-type'] == 'application/json'
    assert cbmock.called

    initial_result = initial_request.json()
    provider_id = initial_result['provider_id']
    reference = initial_result['reference']

    # Complete the check
    complete_request = session.post(f'http://app/docfetch/checks/{check_id}/complete', json={
        'id': check_id,
        'provider_id': provider_id,
        'reference': reference,
        'commercial_relationship': 'DIRECT',
        'provider_config': provider_config,
        'custom_data': initial_result['custom_data']
    }, auth=auth())
    assert complete_request.status_code == 200
    assert complete_request.headers['content-type'] == 'application/json'
    
    complete_result = complete_request.json()

    documents = complete_result['check_output']['documents']
    assert len(documents) == 1
    assert documents[0]['verification_result']['all_passed']
    assert len(documents[0]['images']) > 0
    image_reference = documents[0]['images'][0]['provider_reference']

    # Download the image
    complete_request = session.post('http://app/docfetch/download_image', json={
        'check_id': check_id,
        'image_reference': image_reference,
        'commercial_relationship': 'DIRECT',
        'provider_config': provider_config,
        'custom_data': initial_result['custom_data']
    }, auth=auth())
    assert complete_request.status_code == 200
    assert complete_request.headers['content-type'] == 'image/png'
    
    image_data = complete_request.content

    assert len(image_data) > 0
