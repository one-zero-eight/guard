import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel

from src.api.dependencies import VerifyTokenDep
from src.config import settings
from src.logging_ import logger

router = APIRouter(prefix="/google", tags=["Google"], route_class=AutoDeriveResponsesAPIRoute)

Role = Literal["writer", "reader"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

spreadsheet_roles: dict[str, Role] = {}


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
    spreadsheet_id: str
    "Spreadsheet ID to join"


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


@router.get("/", response_class=HTMLResponse)
def index():
    """Admin interface for setting up Google Sheets integration."""
    template_path = "admin_setup_template.html"
    with open(template_path) as f:
        template_content = f.read()
    return HTMLResponse(template_content)


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
def setup_spreadsheet(
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

        spreadsheet_roles[request.spreadsheet_id] = request.respondent_role

        sheets = sheets_service()
        target_title = "Hello from InNoHassle Guard"

        meta = (
            sheets.spreadsheets()
            .get(spreadsheetId=request.spreadsheet_id, fields="sheets(properties(title,sheetId))")
            .execute()
        )
        titles = {s["properties"]["title"] for s in meta.get("sheets", [])}

        reqs = []
        if target_title not in titles:
            reqs.append({"addSheet": {"properties": {"title": target_title}}})
        if reqs:
            sheets.spreadsheets().batchUpdate(spreadsheetId=request.spreadsheet_id, body={"requests": reqs}).execute()

        join_link = f"https://innohassle.ru/guard/google/join-document?spreadsheet_id={request.spreadsheet_id}"

        description_text = [
            ["📋 InNoHassle Guard Service"],
            [""],
            ["Welcome! This service helps manage secure access to your Google Spreadsheet."],
            [""],
            ["═══════════════════════════════════════════════════════════════════════════════"],
            [""],
            ["📝 INSTRUCTIONS FOR RESPONDENTS:"],
            [""],
            ["To edit this spreadsheet, you must:"],
            ["   1️⃣  Click the join link below"],
            ["   2️⃣  Connect your Gmail account (required - only Gmail addresses work!)"],
            ["   3️⃣  After connecting, you'll get access to edit this spreadsheet"],
            [""],
            ["⚠️  Important: You MUST use a Gmail address (@gmail.com) to access this spreadsheet."],
            ["              Other email providers will not work."],
            [""],
            ["🔗 Join Link:"],
            [join_link],
            [""],
            ["═══════════════════════════════════════════════════════════════════════════════"],
            [""],
            ["📊 Access level for respondents: " + request.respondent_role.upper()],
            [""],
            ["💬 For support, contact: https://t.me/one_zero_eight"],
        ]

        sheets.spreadsheets().values().update(
            spreadsheetId=request.spreadsheet_id,
            range=f"'{target_title}'!A1",
            valueInputOption="RAW",
            body={"values": description_text},
        ).execute()

        sheet_id = None
        for sheet in meta.get("sheets", []):
            if sheet["properties"]["title"] == target_title:
                sheet_id = sheet["properties"]["sheetId"]
                break
        if sheet_id is None:
            meta = (
                sheets.spreadsheets().get(spreadsheetId=request.spreadsheet_id, fields="sheets(properties)").execute()
            )
            for sheet in meta.get("sheets", []):
                if sheet["properties"]["title"] == target_title:
                    sheet_id = sheet["properties"]["sheetId"]
                    break

        format_requests = [
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.26, "green": 0.52, "blue": 0.96},
                            "textFormat": {
                                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                                "fontSize": 11,
                                "bold": True,
                            },
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
                    "properties": {"pixelSize": 40},
                    "fields": "pixelSize",
                }
            },
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 6, "endRowIndex": 7},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 1, "green": 0.95, "blue": 0.8},
                            "textFormat": {"fontSize": 11, "bold": True},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            },
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 13, "endRowIndex": 15},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 1, "green": 0.92, "blue": 0.92},
                            "textFormat": {"fontSize": 11, "bold": True},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            },
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 16, "endRowIndex": 18},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.85, "green": 0.92, "blue": 0.83},
                            "textFormat": {"fontSize": 11, "bold": True},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            },
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 21, "endRowIndex": 22},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                            "textFormat": {"fontSize": 11, "bold": True},
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            },
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 2, "endRowIndex": 3},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"fontSize": 11, "bold": False},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat)",
                }
            },
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 8, "endRowIndex": 12},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"fontSize": 11, "bold": False},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat)",
                }
            },
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 17, "endRowIndex": 18},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"fontSize": 11, "bold": False},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat)",
                }
            },
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 23, "endRowIndex": 24},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"fontSize": 11, "bold": False},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat)",
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                    "properties": {"pixelSize": 900},
                    "fields": "pixelSize",
                }
            },
        ]

        sheets.spreadsheets().batchUpdate(
            spreadsheetId=request.spreadsheet_id, body={"requests": format_requests}
        ).execute()

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


@router.get("/join-document", response_class=HTMLResponse)
def join_document_page():
    """Frontend page for respondents to join the spreadsheet."""
    template_path = "join_document_template.html"
    with open(template_path) as f:
        template_content = f.read()
    return HTMLResponse(template_content)


@router.post("/join-document")
def join_document(
    request: JoinDocumentRequest,
    user_data: VerifyTokenDep,
):
    """Add user to the spreadsheet with specified role."""
    user_token_data, _token = user_data

    try:
        role = spreadsheet_roles.get(request.spreadsheet_id, "reader")

        logger.info(
            f"User {user_token_data.innohassle_id} (innopolis: {user_token_data.email}) "
            f"adding gmail: {request.gmail} to spreadsheet {request.spreadsheet_id} as {role}"
        )

        drive = drive_service()

        drive.permissions().create(
            fileId=request.spreadsheet_id,
            body={"type": "user", "role": role, "emailAddress": request.gmail},
            sendNotificationEmail=False,
        ).execute()

        logger.info(
            f"Successfully added {request.gmail} as {role} to spreadsheet {request.spreadsheet_id} "
            f"by user {user_token_data.innohassle_id}"
        )

        return {"message": f"Successfully added {request.gmail} as {role}"}

    except HttpError as e:
        logger.error(
            f"Google API error: user {user_data[0].innohassle_id} tried to add {request.gmail} "
            f"to spreadsheet {request.spreadsheet_id}: {e}"
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
            f"to spreadsheet {request.spreadsheet_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))
