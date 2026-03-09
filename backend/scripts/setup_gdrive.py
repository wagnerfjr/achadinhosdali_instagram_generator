import os
import os.path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def main():
    """
    Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_secret_file = 'client_secret.json'
            if not os.path.exists(client_secret_file):
                print(f"❌ Erro: Arquivo '{client_secret_file}' não encontrado!")
                print("1. Vá ao Google Cloud Console.")
                print("2. Crie um 'OAuth 2.0 Client ID' para Desktop App.")
                print(f"3. Baixe o JSON e salve como '{client_secret_file}' na raiz do projeto.")
                return

            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
        print("✅ Sucesso! O arquivo 'token.json' foi gerado.")
        print("Agora o projeto usará sua conta pessoal para o upload, utilizando sua cota de espaço.")

if __name__ == '__main__':
    main()
