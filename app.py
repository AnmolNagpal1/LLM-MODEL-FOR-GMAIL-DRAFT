import os
import csv
import base64
import google.generativeai as genai
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from dotenv import load_dotenv
from flask import Flask, request, redirect, url_for, session, render_template
from werkzeug.wrappers import Response  

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key')

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.compose']
GMAIL_CREDENTIALS_FILE = 'credentials.json'


def authenticate_gmail():
    creds = None
    if 'credentials' in session:
        import json
        credentials_info = json.loads(session['credentials'])  # Convert JSON string to dict
        creds = Credentials.from_authorized_user_info(credentials_info, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(
                GMAIL_CREDENTIALS_FILE, scopes=GMAIL_SCOPES,
                redirect_uri=url_for('oauth2callback', _external=True))
            authorization_url, state = flow.authorization_url(
                access_type='offline', include_granted_scopes='true')
            session['state'] = state
            return redirect(authorization_url)
        session['credentials'] = creds.to_json()
    return build('gmail', 'v1', credentials=creds)


@app.route('/oauth2callback')
def oauth2callback():
    state = session.pop('state', None)
    if not state == request.args.get('state'):
        return 'Invalid state parameter.', 401
    flow = Flow.from_client_secrets_file(
        GMAIL_CREDENTIALS_FILE, scopes=GMAIL_SCOPES,
        state=state, redirect_uri=url_for('oauth2callback', _external=True))

    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['credentials'] = credentials.to_json()
    return redirect(url_for('upload_form'))


def initialize_gemini():
    genai.configure(api_key=GEMINI_API_KEY)
    preferred_models = ["models/gemini-2.0-flash-lite", "models/gemini-2.0-flash-lite"]

    print("🔍 Checking for preferred Gemini models...")
    available_models = genai.list_models()

    for model in available_models:
        if model.name in preferred_models and "generateContent" in model.supported_generation_methods:
            print(f"✅ Using model: {model.name}")
            return genai.GenerativeModel(model.name)

    print("❌ Preferred models not found. Trying fallback...")

    for model in available_models:
        if "generateContent" in model.supported_generation_methods:
            print(f"✅ Using fallback model: {model.name}")
            return genai.GenerativeModel(model.name)

    raise RuntimeError("❌ No available Gemini models support generateContent.")


def generate_email_content(gemini_model, contact):
    """Generate personalized email using Gemini"""
    prompt = f"""
    Create a professional email draft with these parameters:
    - Recipient: {contact['Name']} ({contact['Email']})
    - Company: {contact['Company']}
    - Company Details: {contact['Company One Line Detail']}
    - Context: {contact['Message Context']}
    - Tone: Professional but friendly
    - Length: 3 short paragraphs max
    - Include: Personalized opener, value proposition, clear CTA

    Structure:
    Subject: [Effective subject line < 60 characters]

    [Email body]

    Best regards,
    [Your Name]
    [Your Position]
    [Your Contact Info]
    """
    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini API Error: {str(e)}")
        return None


def create_gmail_draft(gmail_service, contact, content):
    """Create draft email in Gmail"""
    try:
        # Split content into subject and body
        content_parts = content.split('\n', 1)
        subject = content_parts[0].replace('Subject:', '').strip()
        body = content_parts[1].strip()

        # Create email message with proper MIME format
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        message = MIMEMultipart()
        message['to'] = f"{contact['Name']} <{contact['Email']}>"
        message['subject'] = subject
        message.attach(MIMEText(body, 'plain'))

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        body = {'raw': raw_message}

        draft = gmail_service.users().drafts().create(
            userId='me',
            body={'message': body}
        ).execute()

        print(f"✅ Draft created for {contact['Name']} (ID: {draft['id']})")
        return True

    except Exception as e:
        print(f"Gmail API Error: {str(e)}")
        return False


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload_form():
    gmail_service = authenticate_gmail()
    if isinstance(gmail_service, Response):
        return gmail_service

    if request.method == 'POST':
        if 'csv_file' not in request.files:
            return 'No file part'
        file = request.files['csv_file']
        if file.filename == '':
            return 'No selected file'
        if file:
            gemini_model = initialize_gemini()
            if not gemini_model:
                return "Failed to initialize Gemini model."

            # Fix: Read the file content properly
            csv_content = file.read().decode('utf-8')
            contacts = csv.DictReader(csv_content.splitlines())
            
            for contact in contacts:
                print(f"\n✍️ Processing {contact['Name']}...")
                email_content = generate_email_content(gemini_model, contact)
                if email_content:
                    create_gmail_draft(gmail_service, contact, email_content)
                else:
                    print(f"❌ Failed to generate content for {contact['Name']}")
            return render_template('draft_success.html')
    return render_template('upload_form.html')


@app.route('/add_user', methods=['POST'])
def add_cloud_user():
    email = request.form.get('email')
    if add_cloud_console_user(email):
        return "User added successfully"
    return "Failed to add user"

@app.route('/add_test_user', methods=['POST'])
def add_oauth_test_user():
    email = request.form.get('email')
    if add_test_user(email):
        return "Test user added successfully"
    return "Failed to add test user"

if __name__ == '__main__':
    app.run(debug=True)