import requests
import os
import json
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

load_dotenv()

# === Konfigurasi ===
PTERO_PANEL_URL = os.getenv("PTERO_PANEL_URL")
PTERO_API_KEY = os.getenv("PTERO_API_KEY")
SERVER_ID = os.getenv("SERVER_ID")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
# === Google Drive Setup ===
SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")


def auth_google_drive():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=credentials)

def upload_to_drive(filename):
    service = auth_google_drive()

    # Upload file ke dalam folder tertentu
    file_metadata = {
        'name': os.path.basename(filename),
        'parents': [GDRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(filename, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()

    file_id = file.get("id")

    # Set permission: Anyone with the link can view
    permission = {
        'type': 'anyone',
        'role': 'reader'
    }
    service.permissions().create(fileId=file_id, body=permission).execute()

    return file.get("webViewLink")

def notify_discord(message):
    payload = {
        "content": message
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def get_backups():
    headers = {
        "Authorization": f"Bearer {PTERO_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    url = f"{PTERO_PANEL_URL.rstrip('/')}/api/client/servers/{SERVER_ID}/backups"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["data"]

def download_backup(backup):
    headers = {
        "Authorization": f"Bearer {PTERO_API_KEY}",
        "Accept": "application/json"
    }
    uuid = backup["attributes"]["uuid"]
    name = f"{uuid}.tar.gz"
    url = f"{PTERO_PANEL_URL.rstrip('/')}/api/client/servers/{SERVER_ID}/backups/{uuid}/download"
    dl_response = requests.get(url, headers=headers)
    dl_response.raise_for_status()
    direct_url = dl_response.json()["attributes"]["url"]
    data = requests.get(direct_url)
    with open(name, "wb") as f:
        f.write(data.content)
    return name

def main():
    try:
        backups = get_backups()
        if not backups:
            notify_discord("⚠️ Tidak ada backup ditemukan untuk server.")
            return

        for backup in backups:
            created_at = datetime.fromisoformat(backup["attributes"]["created_at"].replace("Z", "+00:00"))
            age = datetime.now(created_at.tzinfo) - created_at
            if age.days >= 0:
                filename = download_backup(backup)
                gdrive_link = upload_to_drive(filename)
                notify_discord(f"✅ Backup `{filename}` telah diupload ke Google Drive:\n{gdrive_link}")
                os.remove(filename)
    except Exception as e:
        notify_discord(f"❌ Terjadi error saat proses backup: {e}")

if __name__ == "__main__":
    main()
