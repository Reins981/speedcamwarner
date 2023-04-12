import json
import os
import io
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from httplib2 import HttpLib2Error, ServerNotFoundError
from typing import Any, Tuple, Union
from Logger import Logger
from socket import gaierror

logger = Logger("ServiceAccount")

BASE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "service_account")
SERVICE_ACCOUNT = os.path.join(BASE_PATH, 'osmwarner-a28ef48350cb.json') # Please set the file of your credentials of service account.
FOLDER_ID = '1VlWuYw_lGeZzrVt5P-dvw8ZzZWSXpaQR' # Please set the folder ID that you shared your folder with the service account.
FILENAME = os.path.join(BASE_PATH, 'cameras.json') # Please set the filename with the path you want to upload.

SCOPES = ['https://www.googleapis.com/auth/drive']
# Define the file ID of the file you want to update
FILE_ID = '1SetcX-p12V7apMD8v8CLWEfdA2SY2bU-'


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
    logger.print_log_line(f"Adding new camera: {new_camera}")

    with open(FILENAME, 'r') as fp:
        content = json.load(fp)

    content['cameras'].append(new_camera)

    with open(FILENAME, 'w') as fp:
        json.dump(content, fp, indent=4, sort_keys=False)


def upload_file_to_google_drive(f_id: str, folder_id: str, drive: Any, file_name: str = None) -> str:
    if isinstance(drive, str):
        return drive

    if file_name is None:
        file_name = FILENAME

    try:
        # Retrieve the current parent folder IDs for the file
        file = drive.files().get(fileId=f_id, fields='parents').execute()
        current_parents = ",".join(file.get('parents'))

        # Add the file to the new parent folder
        file = MediaFileUpload(file_name, resumable=True)
        response = drive.files().update(fileId=f_id, addParents=folder_id,
                                        removeParents=current_parents, media_body=file).execute()
        file_id = response.get('id')

        logger.print_log_line(f'Camera upload success: File ID {file_id} has been moved to '
                              f'folder ID {folder_id}.')
        return 'success'
    except (gaierror, ServerNotFoundError, HttpError) as error:
        return f'An error occurred: {error}'


def download_file_from_google_drive(f_id: str, drive: Any) -> str:
    # Get metadata of the file
    if isinstance(drive, str):
        error = drive
        return error

    try:
        file = drive.files().get(fileId=f_id).execute()
    except (gaierror, ServerNotFoundError, HttpError) as error:
        return str(error)

    # Create a buffer to download the file to
    file_content = io.BytesIO()

    # Get the request instance and URI
    try:
        request = drive.files().get_media(fileId=f_id)
    except HttpError as error:
        return str(error)

    downloader = MediaIoBaseDownload(file_content, request)
    done = False
    # Download the file
    while done is False:
        try:
            status, done = downloader.next_chunk()
            logger.print_log_line(f"Download {int(status.progress() * 100)} % complete.")
        except (HttpError, HttpLib2Error) as error:
            return str(error)

    try:
        save_response_content(file, file_content)
    except Exception as error:
        return str(error)
    return 'success'


def save_response_content(file_meta: Any, file_content: Union[io.BytesIO]):
    # Write the downloaded content to a file
    with open(file_meta['name'], 'wb') as f:
        f.write(file_content.getbuffer())


if __name__ == "__main__":
    add_camera_to_json('FrannkfurterStree', coordinates=(43.758896, -44.985130))
    status = upload_file_to_google_drive(build_drive_from_credentials())
    if status == 'success':
        success = download_file_from_google_drive(FILE_ID, build_drive_from_credentials())


