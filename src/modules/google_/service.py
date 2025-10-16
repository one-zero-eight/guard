import json
from functools import lru_cache

from beanie import PydanticObjectId
from fastapi import HTTPException
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as SaCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import settings
from src.logging_ import logger
from src.modules.google_.constants import FileTypes, HTTPStatuses, UserRoles

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    # "https://www.googleapis.com/auth/documents",
]


@lru_cache(maxsize=1)
def get_sa_creds():
    return SaCredentials.from_service_account_info(
        json.loads(settings.google_service_account_file.read_text()), scopes=SCOPES
    )


@lru_cache(maxsize=1)
def get_user_creds():
    if not settings.google.oauth_token_file:
        raise RuntimeError("google_oauth_token_file is not configured in settings")
    return UserCredentials.from_authorized_user_file(str(settings.google.oauth_token_file), SCOPES)


@lru_cache(maxsize=1)
def sheets_service():
    return build("sheets", "v4", credentials=get_user_creds(), cache_discovery=False)


@lru_cache(maxsize=1)
def drive_service():
    return build("drive", "v3", credentials=get_user_creds(), cache_discovery=False)


@lru_cache(maxsize=1)
def docs_service():
    return build("docs", "v1", credentials=get_user_creds(), cache_discovery=False)


def service_email() -> str:
    """Return email of the authenticated OAuth user via Drive About API."""
    try:
        drive = drive_service()
        about = drive.about().get(fields="user").execute()
        return about.get("user", {}).get("emailAddress", "unknown")
    except Exception as e:
        logger.error(f"Failed to get service email via Drive About API: {e}")
        return "unknown"


def _disable_writers_can_share(file_id: str) -> None:
    drive = drive_service()
    drive.files().update(fileId=file_id, body={"writersCanShare": False}).execute()


def create_spreadsheet(title: str) -> str:
    # Создаём файл как Gmail-владелец через Drive API,
    # так он точно будет жить в диске пользователя
    drive = drive_service()
    body = {
        "name": title,
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }
    # если настроена папка — сохраняем в неё
    if settings.google.drive_folder_id:
        body["parents"] = [settings.google.drive_folder_id]
    file = drive.files().create(body=body, fields="id").execute()
    file_id = file["id"]

    _disable_writers_can_share(file_id)

    logger.info(f"Created spreadsheet {file_id} with title '{title}'")
    return file_id


def create_document(title: str) -> str:
    raise HTTPException(status_code=HTTPStatuses.NOT_IMPLEMENTED, detail="Document creation is not implemented yet")


def create_google_file(file_type: str, title: str) -> str:
    if file_type == FileTypes.SPREADSHEET:
        return create_spreadsheet(title)
    elif file_type == FileTypes.DOCUMENT:
        return create_document(title)
    else:
        raise ValueError(f"Unknown file type: {file_type}")


def verify_file_ownership(file, user_id: str) -> None:
    if str(file.author_id) != user_id:
        raise HTTPException(status_code=HTTPStatuses.FORBIDDEN, detail="You are not the author of this file")


def delete_google_file(file_id: str) -> bool:
    try:
        drive = drive_service()
        drive.files().delete(fileId=file_id).execute()
        logger.info(f"Deleted Google file {file_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {e}")
        return False


def revoke_file_permission(file_id: str, permission_id: str) -> bool:
    try:
        drive = drive_service()
        drive.permissions().delete(fileId=file_id, permissionId=permission_id).execute()
        logger.info(f"Removed Google Drive permission {permission_id}")
        return True
    except Exception as e:
        logger.error(f"Error removing permission {permission_id}: {e}")
        return False


def accept_ownership_if_pending(file_id: str) -> bool:
    drive = drive_service()
    perms = drive.permissions().list(fileId=file_id, fields="permissions(id,emailAddress,role,pendingOwner)").execute()
    for p in perms.get("permissions", []):
        if p.get("pendingOwner"):
            try:
                drive.permissions().update(
                    fileId=file_id,
                    permissionId=p["id"],
                    body={"role": "owner"},
                    transferOwnership=True,
                ).execute()
                logger.info(f"Accepted ownership transfer for {file_id}")
                return True
            except Exception as e:
                logger.error(f"Error accepting ownership for {file_id}: {e}")
                raise
    return False


def remove_public_links_and_lock_sharing(file_id: str) -> int:
    """Remove anyone/anyoneWithLink permissions and disable writersCanShare. Returns removed count."""
    drive = drive_service()
    removed = 0
    perms = drive.permissions().list(fileId=file_id, fields="permissions(id,type,role)").execute()
    for p in perms.get("permissions", []):
        if p.get("type") in {"anyone", "domain"}:
            try:
                drive.permissions().delete(fileId=file_id, permissionId=p["id"]).execute()
                removed += 1
            except Exception as e:
                logger.error(f"Error removing public permission {p['id']} on {file_id}: {e}")
    _disable_writers_can_share(file_id)
    return removed


def count_user_permissions(file_id: str) -> int:
    drive = drive_service()
    perms = drive.permissions().list(fileId=file_id, fields="permissions(id,type)").execute()
    return sum(1 for p in perms.get("permissions", []) if p.get("type") == "user")


def get_user_id_from_token(user_token_data) -> PydanticObjectId:
    return PydanticObjectId(user_token_data.innohassle_id)


def generate_join_link(slug: str) -> str:
    return f"{settings.base_url}/guard/google/files/{slug}/join"


def determine_user_role(file, user_id: PydanticObjectId, requested_role: str) -> str:
    if str(file.author_id) == str(user_id):
        return UserRoles.WRITER
    return requested_role


async def add_user_to_file(file_slug: str, user_id: PydanticObjectId, gmail: str, innomail: str):
    from src.modules.google_.exceptions import InvalidGmailException
    from src.modules.google_.repository import google_file_repository

    file = await google_file_repository.get_by_slug(file_slug)
    if not file:
        raise ValueError(f"File with slug {file_slug} not found")

    role = determine_user_role(file, user_id, file.user_role)

    drive = drive_service()

    try:
        permission = (
            drive.permissions()
            .create(
                fileId=file.file_id,
                body={"type": "user", "role": role, "emailAddress": gmail},
                sendNotificationEmail=False,
            )
            .execute()
        )
    except HttpError as e:
        if e.resp.status == 400 and "invalidSharingRequest" in str(e):
            raise InvalidGmailException(gmail=gmail)
        raise

    permission_id = permission.get("id")

    await google_file_repository.join_user_to_file(
        slug=file_slug,
        user_id=user_id,
        gmail=gmail,
        innomail=innomail,
        permission_id=permission_id,
    )

    logger.info(f"Successfully added {gmail} as {role} to file {file.file_id}")

    return file
