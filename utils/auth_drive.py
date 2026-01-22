"""
Запустіть цей скрипт локально, щоб авторизуватися в Google Drive.
Він створить файл 'token.json', який потім використовуватиме програма.
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Ті самі права доступу
SCOPES = ['https://www.googleapis.com/auth/drive']


def authenticate():
    creds = None
    # Файл token.json зберігає токени доступу користувача.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # Якщо токени недійсні або відсутні - запускаємо вхід через браузер
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secret.json'):
                print("❌ Помилка: Файл 'client_secret.json' не знайдено.")
                print("1. Зайдіть в Google Cloud Console -> Credentials.")
                print("2. Створіть 'OAuth client ID' (Desktop app).")
                print("3. Скачайте JSON і перейменуйте в 'client_secret.json'.")
                return

            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Зберігаємо токен для наступних запусків
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print("✅ Авторизація успішна! Файл 'token.json' створено.")


if __name__ == '__main__':
    authenticate()