# import datetime

from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from googleapiclient.errors import HttpError

from src.api.dependencies import VerifyTokenDep
from src.logging_ import logger
from src.modules.google_.greeting import setup_greeting_sheet
from src.modules.google_.repository import google_link_repository
from src.modules.google_.schemas import (
    GoogleLink,
    GoogleLinkJoinInfo,
    JoinDocumentRequest,
    JoinDocumentResponse,
    ServiceAccountEmailResponse,
    SetupSpreadsheetRequest,
    SetupSpreadsheetResponse,
)
from src.modules.google_.service import (
    add_user_to_document,
    service_email,
    sheets_service,
    verify_service_account_access,
)

router = APIRouter(prefix="/google", tags=["Google"], route_class=AutoDeriveResponsesAPIRoute)


@router.get("/service-account-email")
def get_service_account_email() -> ServiceAccountEmailResponse:
    """Get the service account email address."""
    try:
        email = service_email()
        return ServiceAccountEmailResponse(email=email)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Service account not configured: {e}")


@router.post("/documents")
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
            title=request.title,
        )

        join_link = f"https://innohassle.ru/guard/google/documents/{link.slug}/join"

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


@router.get("/documents")
async def get_documents(
    user_data: VerifyTokenDep,
) -> list[GoogleLink]:
    """Get all documents for the user (brief info without joins and banned)."""
    user_token_data, _token = user_data
    try:
        links = await google_link_repository.get_by_author_id(user_token_data.innohassle_id)
        return [
            GoogleLink(
                author_id=link.author_id,
                user_role=link.user_role,
                slug=link.slug,
                spreadsheet_id=link.spreadsheet_id,
                title=link.title,
                expire_at=link.expire_at,
                joins_count=len(link.joins or []),
                banned_count=len(link.banned or []),
            )
            for link in links
        ]
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{slug}")
async def get_document(
    slug: str,
    user_data: VerifyTokenDep,
) -> GoogleLink:
    """Get full document information including joins and banned users."""
    user_token_data, _token = user_data
    try:
        link = await google_link_repository.get_by_slug(slug)

        if not link:
            raise HTTPException(status_code=404, detail="Document not found")

        if str(link.author_id) != user_token_data.innohassle_id:
            raise HTTPException(status_code=403, detail="You are not the author of this document")

        return GoogleLink(
            author_id=link.author_id,
            user_role=link.user_role,
            slug=link.slug,
            spreadsheet_id=link.spreadsheet_id,
            title=link.title,
            expire_at=link.expire_at,
            joins=[
                GoogleLinkJoinInfo(
                    user_id=join.user_id,
                    gmail=join.gmail,
                    innomail=join.innomail,
                    joined_at=join.joined_at,
                )
                for join in link.joins
            ],
            banned=link.banned,
            joins_count=len(link.joins or []),
            banned_count=len(link.banned or []),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{slug}/joins")
async def join_document(
    request: JoinDocumentRequest,
    user_data: VerifyTokenDep,
    slug: str,
) -> JoinDocumentResponse:
    """Add user to the spreadsheet with specified role."""
    user_token_data, _token = user_data

    try:
        logger.info(
            f"User {user_token_data.innohassle_id} (innopolis: {user_token_data.email}) "
            f"adding gmail: {request.gmail} to document {slug}"
        )

        link = await add_user_to_document(
            slug=slug,
            user_id=user_token_data.innohassle_id,
            gmail=request.gmail,
            innomail=user_token_data.email,
        )

        logger.info(
            f"Successfully added {request.gmail} as {link.user_role} to spreadsheet {link.spreadsheet_id} "
            f"by user {user_token_data.innohassle_id} (innopolis: {user_token_data.email})"
        )

        return JoinDocumentResponse(
            message=f"Successfully added {request.gmail} as {link.user_role}",
            spreadsheet_id=link.spreadsheet_id,
        )

    except HttpError as e:
        logger.error(
            f"Google API error: user {user_token_data.innohassle_id} tried to add {request.gmail} "
            f"to document {slug}: {e}"
        )
        if e.resp.status == 403:
            raise HTTPException(
                status_code=403,
                detail="Permission denied. Make sure the service account has access to the spreadsheet.",
            )
        if e.resp.status == 404:
            raise HTTPException(status_code=404, detail="Spreadsheet not found.")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error: user {user_token_data.innohassle_id} tried to add {request.gmail} to document {slug}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))
