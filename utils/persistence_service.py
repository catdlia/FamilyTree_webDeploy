import os
import shutil
import io
import streamlit as st
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# Константи
SCOPES = ['https://www.googleapis.com/auth/drive']
TOKEN_FILE = 'token.json'
LOCAL_DATA_DIR = 'family_tree_data'
ROOT_FOLDER_NAME = 'FamilyTreeBackup'


class PersistenceService:
    def __init__(self):
        self.creds = None
        self.service = None
        self.is_enabled = False
        self.root_folder_id = None
        self.status = "Ініціалізація..."
        self._authenticate()

    def _authenticate(self):
        try:
            # 1. Отримуємо ID папки
            if 'backup_folder_id' in st.secrets:
                self.root_folder_id = st.secrets['backup_folder_id']

            # 2. АВТОРИЗАЦІЯ
            if os.path.exists(TOKEN_FILE):
                # Локальний режим
                self.creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
                self.status = "Авторизовано через локальний файл"
            elif 'gcp_token' in st.secrets:
                # Режим деплою (Streamlit Cloud)
                # КРИТИЧНО: Примусова конвертація AttrDict у чистий dict
                raw_token = st.secrets['gcp_token']
                token_info = {
                    "token": str(raw_token.get("token", "")),
                    "refresh_token": str(raw_token.get("refresh_token", "")),
                    "token_uri": str(raw_token.get("token_uri", "https://oauth2.googleapis.com/token")),
                    "client_id": str(raw_token.get("client_id", "")),
                    "client_secret": str(raw_token.get("client_secret", "")),
                    "scopes": list(raw_token.get("scopes", SCOPES)),
                }
                
                # Додаткові поля, якщо вони є
                if "universe_domain" in raw_token:
                    token_info["universe_domain"] = str(raw_token["universe_domain"])
                if "account" in raw_token:
                    token_info["account"] = str(raw_token["account"])
                if "expiry" in raw_token:
                    token_info["expiry"] = str(raw_token["expiry"])

                self.creds = Credentials.from_authorized_user_info(token_info, SCOPES)
                self.status = "Авторизовано через Secrets"
            
            # 3. Оновлення токена, якщо він протух
            if self.creds:
                if self.creds.expired and self.creds.refresh_token:
                    try:
                        self.creds.refresh(Request())
                        self.status += " (Токен оновлено)"
                    except Exception as e:
                        self.status = f"Помилка оновлення токена: {e}"
                        self.creds = None

                if self.creds and self.creds.valid:
                    self.service = build('drive', 'v3', credentials=self.creds)
                    self.is_enabled = True
                else:
                    self.is_enabled = False
                    if "Помилка" not in self.status:
                        self.status = "Токен недійсний. Перезапустіть auth_drive.py локально."
            else:
                self.status = "Токен відсутній у файлах та секретах."
                self.is_enabled = False

        except Exception as e:
            self.status = f"Критична помилка автентифікації: {e}"
            self.is_enabled = False

    # Решта методів (_get_or_create_folder, _upload_recursive і т.д.) залишаються без змін
    def _get_or_create_folder(self, folder_name, parent_id):
        if not self.service: return None
        q = f"name = '{folder_name}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = self.service.files().list(q=q, fields="files(id)").execute()
        items = results.get('files', [])
        if items: return items[0]['id']
        else:
            metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent_id]}
            folder = self.service.files().create(body=metadata, fields='id').execute()
            return folder.get('id')

    def _upload_recursive(self, local_path, parent_drive_id):
        if not os.path.exists(local_path): return
        for item in os.listdir(local_path):
            item_path = os.path.join(local_path, item)
            if os.path.isfile(item_path):
                media = MediaFileUpload(item_path, resumable=True)
                metadata = {'name': item, 'parents': [parent_drive_id]}
                self.service.files().create(body=metadata, media_body=media, fields='id').execute()
            elif os.path.isdir(item_path):
                new_folder_id = self._get_or_create_folder(item, parent_drive_id)
                self._upload_recursive(item_path, new_folder_id)

    def upload_backup(self):
        if not self.is_enabled or not self.service or not self.root_folder_id: return False
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_folder_name = f"Backup_{timestamp}"
            backup_id = self._get_or_create_folder(backup_folder_name, self.root_folder_id)
            self._upload_recursive(LOCAL_DATA_DIR, backup_id)
            return True
        except Exception as e:
            st.error(f"Upload failed: {e}")
            return False

    def _download_recursive(self, drive_folder_id, local_path):
        if not os.path.exists(local_path): os.makedirs(local_path, exist_ok=True)
        q = f"'{drive_folder_id}' in parents and trashed = false"
        results = self.service.files().list(q=q, fields="files(id, name, mimeType)").execute()
        for item in results.get('files', []):
            local_item_path = os.path.join(local_path, item['name'])
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                self._download_recursive(item['id'], local_item_path)
            else:
                request = self.service.files().get_media(fileId=item['id'])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False: _, done = downloader.next_chunk()
                with open(local_item_path, 'wb') as f: f.write(fh.getbuffer())

    def download_latest_backup(self):
        if not self.is_enabled or not self.root_folder_id: return False
        try:
            q = f"'{self.root_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            results = self.service.files().list(q=q, orderBy="createdTime desc", pageSize=1, fields="files(id, name)").execute()
            items = results.get('files', [])
            if not items: return False
            if os.path.exists(LOCAL_DATA_DIR): shutil.rmtree(LOCAL_DATA_DIR)
            self._download_recursive(items[0]['id'], LOCAL_DATA_DIR)
            return True
        except Exception: return False
