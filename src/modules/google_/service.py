import json

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


async def add_user_to_document(slug: str, user_id: PydanticObjectId, gmail: str, innomail: str):
    from src.modules.google_.exceptions import InvalidGmailException
    from src.modules.google_.repository import google_link_repository

    link = await google_link_repository.get_by_slug(slug)
    if not link:
        raise ValueError(f"Document with slug {slug} not found")

    drive = drive_service()
    try:
        permission = (
            drive.permissions()
            .create(
                fileId=link.spreadsheet_id,
                body={"type": "user", "role": link.user_role, "emailAddress": gmail},
                sendNotificationEmail=False,
            )
            .execute()
        )
    except HttpError as e:
        if e.resp.status == 400 and "invalidSharingRequest" in str(e):
            raise InvalidGmailException(gmail=gmail)
        raise

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
