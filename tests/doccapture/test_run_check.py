from uuid import uuid4
from unittest.mock import patch

@patch('app.shared.task_thread')
def test_run_check_smoke(cbmock, session, auth):
    # Start the check
    r = session.post('http://app/doccapture/checks', json={
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
        'demo_result': 'DOCUMENT_ALL_CATEGORIES_ALL_PASS'
    }, auth=auth())
    assert r.status_code == 200
    assert r.headers['content-type'] == 'application/json'

    res = r.json()

    assert res['errors'] == []
    assert cbmock.called

@patch('app.shared.task_thread')
def test_retrieve_demo_from_finish_endpoint(cbmock, session, auth):
    check_id = str(uuid4())
    provider_config = {
        'require_dob': False,
        'require_address': False,
    }
    # Start the check
    initial_request = session.post('http://app/doccapture/checks', json={
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
        'demo_result': 'DOCUMENT_ALL_CATEGORIES_ALL_PASS'
    }, auth=auth())
    assert initial_request.status_code == 200
    assert initial_request.headers['content-type'] == 'application/json'
    assert cbmock.called

    initial_result = initial_request.json()
    provider_id = initial_result['provider_id']
    reference = initial_result['reference']

    # Complete the check
    complete_request = session.post(f'http://app/doccapture/checks/{check_id}/complete', json={
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

    assert len(complete_result['check_output']['documents']) == 2
    assert complete_result['check_output']['documents'][0]['verification_result']['all_passed']

@patch('app.shared.task_thread')
def test_download_files(cbmock, session, auth):
    check_id = str(uuid4())
    provider_config = {
        'require_dob': False,
        'require_address': False,
    }
    # Start the check
    initial_request = session.post('http://app/doccapture/checks', json={
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
        'demo_result': 'DOCUMENT_ALL_CATEGORIES_ALL_PASS'
    }, auth=auth())
    assert initial_request.status_code == 200
    assert initial_request.headers['content-type'] == 'application/json'
    assert cbmock.called

    initial_result = initial_request.json()
    provider_id = initial_result['provider_id']
    reference = initial_result['reference']

    # Complete the check
    complete_request = session.post(f'http://app/doccapture/checks/{check_id}/complete', json={
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
    assert len(documents) == 2

    assert 'PROOF_OF_IDENTITY' in {document['category'] for document in documents}
    assert 'PROOF_OF_ADDRESS' in {document['category'] for document in documents}

    for document in documents:
        if document['category'] == 'PROOF_OF_ADDRESS':
            address_document = document
        elif document['category'] == 'PROOF_OF_IDENTITY':
            identity_document = document

    # Test address document
    assert address_document['verification_result']['all_passed']
    assert len(address_document['images']) > 0
    image_reference = address_document['images'][0]['provider_reference']

    assert len(address_document['files']) == 2

    # Download the image for address document
    download_image_request = session.post('http://app/doccapture/download_file', json={
        'check_id': check_id,
        'file_reference': image_reference,
        'download_info': {
            'download_type': 'IMAGE',
            'image_type': address_document['images'][0]['image_type']
        },
        'commercial_relationship': 'DIRECT',
        'provider_config': provider_config,
        'custom_data': initial_result['custom_data']
    }, auth=auth())
    assert download_image_request.status_code == 200
    assert download_image_request.headers['content-type'] == 'image/png'
    assert 'demo_image_address_pass.png' in download_image_request.headers["Content-Disposition"]
    
    image_data = download_image_request.content

    assert len(image_data) > 0

    # Download the video frame for the address document
    video_frame = next(filter(lambda f: f['type'] == 'VIDEO_FRAME', address_document['files']))
    assert video_frame is not None
    download_frame_request = session.post('http://app/doccapture/download_file', json={
        'check_id': check_id,
        'file_reference': video_frame['reference'],
        'download_info': {
            'download_type': 'FILE',
            'file_type': 'VIDEO_FRAME'
        },
        'commercial_relationship': 'DIRECT',
        'provider_config': provider_config,
        'custom_data': initial_result['custom_data']
    }, auth=auth())
    assert download_frame_request.status_code == 200
    assert download_frame_request.headers['content-type'] == 'image/png'
    assert 'demo_image_address_pass.png' in download_frame_request.headers["Content-Disposition"]

    frame_data = download_frame_request.content

    assert len(frame_data) > 0

    # Test identity document
    assert identity_document['verification_result']['all_passed']
    assert len(identity_document['images']) > 0
    image_reference = identity_document['images'][0]['provider_reference']

    assert len(identity_document['files']) == 2

    # Download the image for identity document
    download_image_request = session.post('http://app/doccapture/download_file', json={
        'check_id': check_id,
        'file_reference': image_reference,
        'download_info': {
            'download_type': 'IMAGE',
            'image_type': documents[0]['images'][0]['image_type']
        },
        'commercial_relationship': 'DIRECT',
        'provider_config': provider_config,
        'custom_data': initial_result['custom_data']
    }, auth=auth())
    assert download_image_request.status_code == 200
    assert download_image_request.headers['content-type'] == 'image/png'
    assert 'demo_image_identity_pass.png' in download_image_request.headers["Content-Disposition"]
    
    image_data = download_image_request.content

    assert len(image_data) > 0

    # Download the video frame for the identity document
    video_frame = next(filter(lambda f: f['type'] == 'VIDEO_FRAME', identity_document['files']))
    assert video_frame is not None
    download_frame_request = session.post('http://app/doccapture/download_file', json={
        'check_id': check_id,
        'file_reference': video_frame['reference'],
        'download_info': {
            'download_type': 'FILE',
            'file_type': 'VIDEO_FRAME'
        },
        'commercial_relationship': 'DIRECT',
        'provider_config': provider_config,
        'custom_data': initial_result['custom_data']
    }, auth=auth())
    assert download_frame_request.status_code == 200
    assert download_frame_request.headers['content-type'] == 'image/png'
    assert 'demo_image_identity_pass.png' in download_frame_request.headers["Content-Disposition"]

    frame_data = download_frame_request.content

    assert len(frame_data) > 0

    # Download the live video (same for both docs)
    live_video = next(filter(lambda f: f['type'] == 'LIVE_VIDEO', documents[0]['files']))
    assert live_video is not None
    download_video_request = session.post('http://app/doccapture/download_file', json={
        'check_id': check_id,
        'file_reference': live_video['reference'],
        'download_info': {
            'download_type': 'FILE',
            'file_type': 'LIVE_VIDEO'
        },
        'commercial_relationship': 'DIRECT',
        'provider_config': provider_config,
        'custom_data': initial_result['custom_data']
    }, auth=auth())
    assert download_video_request.status_code == 200
    assert download_video_request.headers['content-type'] == 'video/mp4'

    video_data = download_video_request.content

    assert len(video_data) > 0
