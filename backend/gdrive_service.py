import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from .logger import setup_logger

logger = setup_logger("gdrive")

class GoogleDriveService:
    def __init__(self):
        self.folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        self.token_file = "token.json"
        self.service_account_file = "credencials.json"
        self.service = None
        
        if not self.folder_id:
            logger.error("GOOGLE_DRIVE_FOLDER_ID not found in .env")
            return

        try:
            scopes = ['https://www.googleapis.com/auth/drive.file']
            creds = None
            
            # 1. Try OAuth2 User Token (Solves Quota Issue)
            if os.path.exists(self.token_file):
                logger.info("Using OAuth2 User Token (Personal Account Quota)")
                from google.oauth2.credentials import Credentials
                from google.auth.transport.requests import Request
                creds = Credentials.from_authorized_user_file(self.token_file, scopes)
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
            
            # 2. Fallback to Service Account (Might fail with 403 Quota on personal drives)
            elif os.path.exists(self.service_account_file):
                logger.info("Using Service Account (Note: Personal drives may hit quota limits)")
                creds = service_account.Credentials.from_service_account_file(
                    self.service_account_file, scopes=scopes)
            
            if creds:
                self.service = build('drive', 'v3', credentials=creds)
                logger.info("Google Drive API service initialized successfully.")
            else:
                logger.error("No Google Drive credentials found (token.json or credencials.json)")
                
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            self.service = None

    def upload_file(self, file_path: str, mime_type: str = 'application/octet-stream') -> str:
        """Uploads a file to the configured Google Drive folder."""
        if not self.service or not self.folder_id:
            logger.error("Google Drive service NOT available or Folder ID missing.")
            return None

        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [self.folder_id]
        }
        
        try:
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            file = self.service.files().create(body=file_metadata,
                                                media_body=media,
                                                fields='id').execute()
            file_id = file.get('id')
            logger.info(f"File uploaded to Google Drive. ID: {file_id}")
            return file_id
        except Exception as e:
            logger.error(f"Error uploading file to Google Drive: {e}")
            return None
