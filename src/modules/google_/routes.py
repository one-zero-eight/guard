import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel

from src.api.dependencies import VerifyTokenDep
from src.config import settings
from src.logging_ import logger
from src.modules.google_.greeting import setup_greeting_sheet
from src.modules.google_.repository import google_link_repository

router = APIRouter(prefix="/google", tags=["Google"], route_class=AutoDeriveResponsesAPIRoute)

Role = Literal["writer", "reader"]

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


class JoinDocumentRequest(BaseModel):
    gmail: str
    "Gmail address to add to the spreadsheet"


class ServiceAccountEmailResponse(BaseModel):
    email: str
    "Service account email address"


class SetupSpreadsheetRequest(BaseModel):
    spreadsheet_id: str
    "Spreadsheet ID to setup"
    respondent_role: Role
    "Role for respondents (writer or reader)"


class SetupSpreadsheetResponse(BaseModel):
    sheet_title: str
    "Title of the created sheet"
    spreadsheet_id: str
    "Spreadsheet ID"
    role_display: str
    "Role display name"
    join_link: str
    "Join link for respondents"


@router.get("/service-account-email")
def get_service_account_email() -> ServiceAccountEmailResponse:
    """Get the service account email address."""
    try:
        email = service_email()
        return ServiceAccountEmailResponse(email=email)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Service account not configured: {e}")


def verify_service_account_access(spreadsheet_id: str) -> bool:
    """Check if the service account has access to the spreadsheet."""
    try:
        drive = drive_service()
        permissions = drive.permissions().list(fileId=spreadsheet_id, fields="permissions(emailAddress)").execute()
        service_acc_email = service_email()
        return any(p.get("emailAddress") == service_acc_email for p in permissions.get("permissions", []))
    except HttpError:
        return False


@router.post("/setup-spreadsheet")
async def setup_spreadsheet(
    request: SetupSpreadsheetRequest,
    user_data: VerifyTokenDep,
) -> SetupSpreadsheetResponse:
    """Setup InNoHassle Guard sheet with description and return join link."""
    user_token_data, _token = user_data

    try:
        logger.info(
            f"User {user_token_data.innohassle_id} (email: {user_token_data.email}) "
            f"setting up spreadsheet {request.spreadsheet_id} with role {request.respondent_role}"
        )

        if not verify_service_account_access(request.spreadsheet_id):
            raise HTTPException(
                status_code=403,
                detail=f"Service account {service_email()} does not have access to this spreadsheet. "
                "Please add the service account as an editor to the spreadsheet first.",
            )

        link = await google_link_repository.setup_spreadsheet(
            author_id=user_token_data.innohassle_id,
            user_role=request.respondent_role,
            spreadsheet_id=request.spreadsheet_id,
        )

        join_link = f"https://innohassle.ru/guard/google/join-document/{link.slug}"

        sheets = sheets_service()
        target_title = setup_greeting_sheet(
            sheets_service=sheets,
            spreadsheet_id=request.spreadsheet_id,
            join_link=join_link,
            respondent_role=request.respondent_role,
        )

        return SetupSpreadsheetResponse(
            sheet_title=target_title,
            spreadsheet_id=request.spreadsheet_id,
            role_display=request.respondent_role,
            join_link=join_link,
        )
    except HttpError as e:
        logger.error(f"Google API error: {e}")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        logger.error(f"Setup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/join-document/{slug}")
async def join_document(
    request: JoinDocumentRequest,
    user_data: VerifyTokenDep,
    slug: str,
):
    """Add user to the spreadsheet with specified role."""
    user_token_data, _token = user_data

    try:
        link = await google_link_repository.get_by_slug(slug)

        logger.info(
            f"User {user_token_data.innohassle_id} (innopolis: {user_token_data.email}) "
            f"adding gmail: {request.gmail} to spreadsheet {link.spreadsheet_id} as {link.user_role}"
        )

        drive = drive_service()

        drive.permissions().create(
            fileId=link.spreadsheet_id,
            body={"type": "user", "role": link.user_role, "emailAddress": request.gmail},
            sendNotificationEmail=False,
        ).execute()

        logger.info(
            f"Successfully added {request.gmail} as {link.user_role} to spreadsheet {link.spreadsheet_id} "
            f"by user {user_token_data.innohassle_id} (innopolis: {user_token_data.email})"
        )

        return {"message": f"Successfully added {request.gmail} as {link.user_role}"}

    except HttpError as e:
        logger.error(
            f"Google API error: user {user_data[0].innohassle_id} tried to add {request.gmail} "
            f"to spreadsheet {link.spreadsheet_id}: {e}"
        )
        if e.resp.status == 403:
            raise HTTPException(
                status_code=403,
                detail="Permission denied. Make sure the service account has access to the spreadsheet.",
            )
        if e.resp.status == 404:
            raise HTTPException(status_code=404, detail="Spreadsheet not found.")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error: user {user_token_data.innohassle_id} tried to add {request.gmail} "
            f"to spreadsheet {link.spreadsheet_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))
