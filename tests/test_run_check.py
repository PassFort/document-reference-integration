from uuid import uuid4

def test_run_check_smoke(session, auth):
    r = session.post('http://app/checks', json={
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
            'documents': [
                {
                    'category': 'PROOF_OF_IDENTITY',
                    'document_type': 'PASSPORT',
                    'id': str(uuid4())
                }
            ]
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

def test_retrieve_demo_from_finish_endpoint(session, auth):
    initial_request = session.post('http://app/checks', json={
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
            'documents': [
                {
                    'category': 'PROOF_OF_IDENTITY',
                    'document_type': 'PASSPORT',
                    'id': str(uuid4())
                }
            ]
        },
        'commercial_relationship': 'DIRECT',
        'provider_config': {
            'require_dob': False,
            'require_address': False,
        },
        'demo_result': 'DOCUMENT_ALL_PASS'
    }, auth=auth())
    assert initial_request.status_code == 200
    assert initial_request.headers['content-type'] == 'application/json'

    initial_result = initial_request.json()
    check_id = initial_result['provider_id']
    
    complete_request = session.post('http://app/checks/458f7eb3-d686-4515-b6ac-5dfb1ff4dc70/complete', json={
        'id': check_id,
        'reference': 'DEMODATA',
        'custom_data': initial_result['custom_data']
    }, auth=auth())
    assert complete_request.status_code == 200
    assert complete_request.headers['content-type'] == 'application/json'
    
    complete_result = complete_request.json()

    assert len(complete_result['check_output']['documents']) == 1
    assert complete_result['check_output']['documents'][0]['verification_result']['all_passed']


