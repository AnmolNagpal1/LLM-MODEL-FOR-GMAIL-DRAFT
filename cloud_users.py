from google.oauth2 import service_account
from googleapiclient.discovery import build

def add_cloud_console_user(email, role='roles/viewer'):
    """Add a user to Google Cloud Console with specified role"""
    credentials = service_account.Credentials.from_service_account_file(
        'service-account.json',
        scopes=['https://www.googleapis.com/auth/cloud-platform']
    )
    
    service = build('cloudidentity', 'v1', credentials=credentials)
    
    request_body = {
        'role': role,
        'member': f'user:{email}'
    }
    
    try:
        service.projects().setIamPolicy(
            resource=f'projects/{PROJECT_ID}',
            body={'policy': request_body}
        ).execute()
        return True
    except Exception as e:
        print(f"Error adding user: {str(e)}")
        return False