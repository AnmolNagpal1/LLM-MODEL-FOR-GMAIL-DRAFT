from google.oauth2 import service_account
from googleapiclient.discovery import build

def add_test_user(email):
    """Add authorized test user to OAuth consent screen"""
    credentials = service_account.Credentials.from_service_account_file(
        'service-account.json',
        scopes=['https://www.googleapis.com/auth/cloud-platform']
    )
    
    service = build('iamcredentials', 'v1', credentials=credentials)
    
    project_id = '39366' 
    
    request_body = {
        'testUsers': [{
            'email': email,
            'status': 'APPROVED'
        }]
    }
    
    try:
        service.projects().brands().authorizedTestUsers().create(
            parent=f'projects/{project_id}',
            body=request_body
        ).execute()
        return True
    except Exception as e:
        print(f"Error adding test user: {str(e)}")
        return False

