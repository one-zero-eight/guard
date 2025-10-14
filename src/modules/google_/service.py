import base64
import json
import re

from beanie import PydanticObjectId
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import settings
from src.logging_ import logger

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_creds():
    return Credentials.from_service_account_info(
        json.loads(settings.google_service_account_file.read_text()), scopes=SCOPES
    )


def sheets_service():
    return build("sheets", "v4", credentials=get_creds(), cache_discovery=False)


def drive_service():
    return build("drive", "v3", credentials=get_creds(), cache_discovery=False)


def service_email() -> str:
    return get_creds().service_account_email


def verify_service_account_access(spreadsheet_id: str) -> bool:
    try:
        drive = drive_service()
        permissions = drive.permissions().list(fileId=spreadsheet_id, fields="permissions(emailAddress)").execute()
        service_acc_email = service_email()
        return any(p.get("emailAddress") == service_acc_email for p in permissions.get("permissions", []))
    except HttpError:
        return False


def decode_photo_link_id(photo_link: str) -> bytes | None:
    try:
        match = re.search(r"://[\w\-\.]+/[\w\-]+/([\w\-\_]+)", photo_link or "")
        if match:
            photo_id = match.group(1)
        else:
            return None

        standard_base64 = photo_id.replace("-", "+").replace("_", "/")
        padding = len(standard_base64) % 4
        if padding:
            standard_base64 += "=" * (4 - padding)

        decoded = base64.b64decode(standard_base64)
        return decoded[:3]
    except Exception:
        logger.error(f"Error decoding photo link id: {photo_link}")
        return None


async def add_user_to_document(slug: str, user_id: PydanticObjectId, gmail: str, innomail: str):
    from src.modules.google_.repository import google_link_repository

    link = await google_link_repository.get_by_slug(slug)
    if not link:
        raise ValueError(f"Document with slug {slug} not found")

    drive = drive_service()
    permission = (
        drive.permissions()
        .create(
            fileId=link.spreadsheet_id,
            body={"type": "user", "role": link.user_role, "emailAddress": gmail},
            sendNotificationEmail=False,
        )
        .execute()
    )

    permission_id = permission.get("id")

    await google_link_repository.add_join(
        slug=slug,
        user_id=user_id,
        gmail=gmail,
        innomail=innomail,
        permission_id=permission_id,
    )

    logger.info(f"Successfully added {gmail} as {link.user_role} to spreadsheet {link.spreadsheet_id}")

    return link
