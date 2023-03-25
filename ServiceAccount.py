import json
import os
import requests
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from typing import Any, Tuple, Union

BASE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "service_account_content")
SERVICE_ACCOUNT = os.path.join(BASE_PATH, 'speedwarner-381612-95bffd9f63e6.json') # Please set the file of your credentials of service account.
FOLDER_ID = '0B5psWkXNfcOycFdhNThOUHJvb1E' # Please set the folder ID that you shared your folder with the service account.
FILENAME = os.path.join(BASE_PATH, 'cameras.json') # Please set the filename with the path you want to upload.
URL = "https://docs.google.com/uc?export=download"

SCOPES = ['https://www.googleapis.com/auth/drive']
# Define the file ID of the file you want to update
FILE_ID = '1dErX2CqcStxMMyKyEke1UkrqvMBznr_T'


def build_drive_from_credentials():
    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT, SCOPES)
        return build('drive', 'v3', credentials=credentials)
    except FileNotFoundError as e:
        return str(e)


def add_camera_to_json(name: str, coordinates: Tuple[float, float]):
    new_camera = \
        {
          "name": name,
          "coordinates": [
            {
              "latitude": coordinates[0],
              "longitude": coordinates[1]
            }
          ]
        }
    print(f"Adding new camera: {new_camera}")

    with open(FILENAME, 'r') as fp:
        content = json.load(fp)

    content['cameras'].append(new_camera)

    with open(FILENAME, 'w') as fp:
        json.dump(content, fp, indent=4, sort_keys=False)


def upload_file_to_google_drive(drive: Any, file_name: str = None) -> str:
    if isinstance(drive, str):
        return drive

    if file_name is None:
        file_name = FILENAME

    try:
        # Retrieve the current parent folder IDs for the file
        file = drive.files().get(fileId=FILE_ID, fields='parents').execute()
        current_parents = ",".join(file.get('parents'))

        # Add the file to the new parent folder
        file = MediaFileUpload(file_name, resumable=True)
        response = drive.files().update(fileId=FILE_ID, addParents=FOLDER_ID,
                                        removeParents=current_parents, media_body=file).execute()
        file_id = response.get('id')

        print(f'Camera upload success: File ID {file_id} has been moved to folder ID {FOLDER_ID}.')
        return 'success'
    except HttpError as error:
        return f'An error occurred: {error}'


def download_file_from_google_drive(f_id: str = None, destination: str = None) -> str:
    session = requests.Session()

    if f_id is None:
        f_id = FILE_ID
    if destination is None:
        destination = FILENAME

    try:
        response = session.get(URL, params={'id': f_id}, stream=True)
    except Exception as error:
        return str(error)
    token = get_confirm_token(response)

    if token:
        params = {'id': f_id, 'confirm': token}
        try:
            response = session.get(URL, params=params, stream=True)
        except Exception as error:
            return str(error)

    return save_response_content(response, destination)


def get_confirm_token(response: Any) -> Union[str, None]:
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value

    return None


def save_response_content(response: Any, destination: str) -> str:
    CHUNK_SIZE = 32768

    with open(destination, "wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk:   # filter out keep-alive new chunks
                #  File has been deleted from drive
                if chunk.decode().startswith("<!doctype html>"):
                    return 'File deleted from google drive'
                else:
                    f.write(chunk)
    return 'success'


if __name__ == "__main__":
    add_camera_to_json('FrannkfurterStree', coordinates=(43.758896, -44.985130))
    status = upload_file_to_google_drive(build_drive_from_credentials())
    if status == 'success':
        success = download_file_from_google_drive(FILE_ID, FILENAME)


