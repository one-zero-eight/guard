# import datetime

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from googleapiclient.errors import HttpError

from src.api.dependencies import VerifyTokenDep
from src.logging_ import logger
from src.modules.google_.greeting import setup_greeting_sheet
from src.modules.google_.repository import google_link_repository
from src.modules.google_.schemas import (
    BanUserRequest,
    BanUserResponse,
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
    drive_service,
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
        if await google_link_repository.get_by_spreadsheet_id(request.spreadsheet_id):
            raise HTTPException(status_code=400, detail="Spreadsheet already setup by another user")

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


@router.delete("/documents/{slug}")
async def delete_document(
    slug: str,
    user_data: VerifyTokenDep,
):
    """Delete a document link by slug (author only)."""
    user_token_data, _token = user_data
    try:
        link = await google_link_repository.get_by_slug(slug)
        if not link:
            raise HTTPException(status_code=404, detail="Document not found")
        if str(link.author_id) != user_token_data.innohassle_id:
            raise HTTPException(status_code=403, detail="You are not the author of this document")

        deleted = await google_link_repository.delete_by_slug(slug)
        if not deleted:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"message": "Document deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
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
                created_at=link.id.generation_time,
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
            created_at=link.id.generation_time,
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
        error_msg = str(e)
        logger.error(f"Validation error: {error_msg}")
        if "banned" in error_msg.lower():
            raise HTTPException(status_code=403, detail="Permission denied. You are banned from this document.")
        raise HTTPException(status_code=404, detail=error_msg)
    except Exception as e:
        logger.error(
            f"Error: user {user_token_data.innohassle_id} tried to add {request.gmail} to document {slug}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{slug}/bans")
async def ban_user(
    slug: str,
    request: BanUserRequest,
    user_data: VerifyTokenDep,
) -> BanUserResponse:
    """Ban user from the document by their innopolis email."""
    user_token_data, _token = user_data

    try:
        link = await google_link_repository.get_by_slug(slug)

        if not link:
            raise HTTPException(status_code=404, detail="Document not found")

        if str(link.author_id) != user_token_data.innohassle_id:
            raise HTTPException(status_code=403, detail="You are not the author of this document")

        join_to_ban = None
        for join in link.joins:
            if join.user_id == request.user_id:
                join_to_ban = join
                break

        if not join_to_ban:
            raise HTTPException(status_code=404, detail=f"User with user_id {request.user_id} not found in joins")

        logger.info(
            f"User {user_token_data.innohassle_id} banning {join_to_ban.gmail} "
            f"(innopolis: {join_to_ban.user_id}) from document {slug}"
        )

        if join_to_ban.permission_id:
            try:
                drive = drive_service()
                drive.permissions().delete(fileId=link.spreadsheet_id, permissionId=join_to_ban.permission_id).execute()
                logger.info(f"Removed Google Drive permission for {join_to_ban.gmail}")
            except Exception as e:
                logger.error(f"Error removing Google Drive permission for {join_to_ban.gmail}: {e}")
                pass

        await google_link_repository.add_banned(slug=slug, user_id=join_to_ban.user_id)

        logger.info(f"Successfully banned {join_to_ban.gmail} (innopolis: {join_to_ban.user_id}) from document {slug}")

        return BanUserResponse(
            message=f"Successfully banned {join_to_ban.user_id}",
        )

    except HTTPException:
        raise
    except HttpError as e:
        logger.error(f"Google API error while banning user: {e}")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        logger.error(f"Error banning user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{slug}/bans/{user_id}")
async def unban_user(
    slug: str,
    user_id: str,
    user_data: VerifyTokenDep,
):
    """Unban user by user_id (author only)."""
    user_token_data, _token = user_data
    try:
        link = await google_link_repository.get_by_slug(slug)
        if not link:
            raise HTTPException(status_code=404, detail="Document not found")
        if str(link.author_id) != user_token_data.innohassle_id:
            raise HTTPException(status_code=403, detail="You are not the author of this document")

        try:
            user_oid = PydanticObjectId(user_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid user_id")

        await google_link_repository.remove_banned(slug=slug, user_id=user_oid)
        return {"message": f"Successfully unbanned {user_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unbanning user: {e}")
        raise HTTPException(status_code=500, detail=str(e))
