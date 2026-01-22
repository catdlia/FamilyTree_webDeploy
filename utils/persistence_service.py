import os
import shutil
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
        self.status = "Initializing..."
        self._authenticate()

    def _authenticate(self):
        try:
            # Спроба отримати ID папки з секретів (якщо є)
            if 'backup_folder_id' in st.secrets:
                self.root_folder_id = st.secrets['backup_folder_id']

            # --- НОВА ЛОГІКА АВТОРИЗАЦІЇ (OAuth2) ---
            if os.path.exists(TOKEN_FILE):
                self.creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

            # Якщо токени протухли, спробуємо оновити (якщо це можливо без браузера)
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    print(f"Token refresh failed: {e}")
                    self.creds = None

            if self.creds and self.creds.valid:
                self.service = build('drive', 'v3', credentials=self.creds)
                self.is_enabled = True
                self.status = "Connected via User Token"
            else:
                self.status = "Token invalid or missing. Run utils/auth_drive.py"
                print(self.status)
                self.is_enabled = False

        except Exception as e:
            self.status = f"Auth Error: {e}"
            print(self.status)
            self.is_enabled = False

    def _get_or_create_folder(self, folder_name, parent_id=None):
        """Знаходить або створює папку на Drive."""
        if not self.service: return None

        q = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            q += f" and '{parent_id}' in parents"

        results = self.service.files().list(q=q, fields="files(id)").execute()
        items = results.get('files', [])

        if items:
            return items[0]['id']
        else:
            metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                metadata['parents'] = [parent_id]

            folder = self.service.files().create(body=metadata, fields='id').execute()
            return folder.get('id')

    def _upload_recursive(self, local_path, parent_drive_id):
        """Рекурсивно завантажує структуру папок."""
        if not os.path.exists(local_path): return

        for item in os.listdir(local_path):
            item_path = os.path.join(local_path, item)

            if os.path.isfile(item_path):
                # Завантаження файлу
                print(f"Uploading file: {item}")
                media = MediaFileUpload(item_path, resumable=True)
                metadata = {'name': item, 'parents': [parent_drive_id]}
                self.service.files().create(
                    body=metadata, media_body=media, fields='id'
                ).execute()

            elif os.path.isdir(item_path):
                # Створення папки
                print(f"Creating folder: {item}")
                new_folder_id = self._get_or_create_folder(item, parent_drive_id)
                self._upload_recursive(item_path, new_folder_id)

    def upload_backup(self):
        """Створює нову папку з датою і заливає туди всі дані."""
        if not self.is_enabled or not self.service:
            st.error(f"Хмара не підключена: {self.status}")
            return False

        try:
            # 1. Отримуємо/Створюємо кореневу папку 'FamilyTreeBackup'
            # (Тепер ми можемо її створити самі, бо ми діємо від імені користувача)
            if self.root_folder_id:
                root_id = self.root_folder_id  # Використовуємо ID з конфігу якщо є
            else:
                root_id = self._get_or_create_folder(ROOT_FOLDER_NAME)

            # 2. Створюємо папку конкретного бекапу з датою
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_folder_name = f"Backup_{timestamp}"

            print(f"Creating backup folder: {backup_folder_name}")
            backup_id = self._get_or_create_folder(backup_folder_name, root_id)

            # 3. Рекурсивно заливаємо вміст
            self._upload_recursive(LOCAL_DATA_DIR, backup_id)
            print(f"Backup complete: {backup_folder_name}")
            return True
        except Exception as e:
            st.error(f"Upload failed: {str(e)}")
            return False

    def _download_recursive(self, drive_folder_id, local_path):
        """Рекурсивно скачує вміст папки."""
        if not os.path.exists(local_path):
            os.makedirs(local_path, exist_ok=True)

        q = f"'{drive_folder_id}' in parents and trashed = false"
        results = self.service.files().list(q=q, fields="files(id, name, mimeType)").execute()
        items = results.get('files', [])

        for item in items:
            item_id = item['id']
            item_name = item['name']
            item_type = item['mimeType']
            local_item_path = os.path.join(local_path, item_name)

            if item_type == 'application/vnd.google-apps.folder':
                self._download_recursive(item_id, local_item_path)
            else:
                print(f"Downloading file: {item_name}")
                request = self.service.files().get_media(fileId=item_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()

                with open(local_item_path, 'wb') as f:
                    f.write(fh.getbuffer())

    def download_latest_backup(self):
        """Знаходить останній бекап."""
        if not self.is_enabled or not self.service: return False

        try:
            # Знаходимо корінь
            if self.root_folder_id:
                root_id = self.root_folder_id
            else:
                # Шукаємо за ім'ям, якщо ID не задано
                q = f"name = '{ROOT_FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
                res = self.service.files().list(q=q).execute()
                if not res.get('files'): return False
                root_id = res.get('files')[0]['id']

            # Шукаємо папки бекапів
            q = f"'{root_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            results = self.service.files().list(
                q=q, orderBy="createdTime desc", pageSize=1, fields="files(id, name)"
            ).execute()

            items = results.get('files', [])
            if not items:
                print("No backups found.")
                return False

            latest_backup = items[0]
            print(f"Downloading latest backup: {latest_backup['name']}")

            if os.path.exists(LOCAL_DATA_DIR):
                shutil.rmtree(LOCAL_DATA_DIR)

            self._download_recursive(latest_backup['id'], LOCAL_DATA_DIR)
            return True

        except Exception as e:
            print(f"Download failed: {e}")
            return False