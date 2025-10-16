from beanie import PydanticObjectId
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from googleapiclient.errors import HttpError

from src.api.dependencies import VerifyTokenDep
from src.logging_ import logger
from src.modules.google_.exceptions import (
    InvalidGmailException,
    UserBannedException,
)
from src.modules.google_.greeting import setup_greeting_sheet
from src.modules.google_.repository import google_file_repository
from src.modules.google_.schemas import (
    BanUserRequest,
    BanUserResponse,
    CleanupResponse,
    CreateFileRequest,
    CreateFileResponse,
    DeleteFileResponse,
    GoogleFile,
    GoogleFileSSOBanInfo,
    GoogleFileSSOJoinInfo,
    HealthCheckResponse,
    JoinFileRequest,
    JoinFileResponse,
    ServiceAccountEmailResponse,
    TransferFileRequest,
    TransferFileResponse,
    UnbanUserResponse,
)
from src.modules.google_.service import (
    accept_ownership_if_pending,
    add_user_to_file,
    count_user_permissions,
    create_google_file,
    delete_google_file,
    generate_join_link,
    get_user_id_from_token,
    remove_public_links_and_lock_sharing,
    revoke_file_permission,
    service_email,
    sheets_service,
    verify_file_ownership,
)

router = APIRouter(prefix="/google", tags=["Google"], route_class=AutoDeriveResponsesAPIRoute)


@router.get("/health")
async def health_check() -> HealthCheckResponse:
    """Health check endpoint to verify service is running."""
    try:
        service_email()
        return HealthCheckResponse(status="healthy", service="google")
    except Exception as e:
        logger.error(f"Health check failed | error={e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@router.get("/service-account-email")
def get_service_account_email() -> ServiceAccountEmailResponse:
    """Get the service account email address."""
    try:
        email = service_email()
        return ServiceAccountEmailResponse(email=email)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Service account not configured: {e}")


@router.post("/files")
async def create_file(
    request: CreateFileRequest,
    user_data: VerifyTokenDep,
    background_tasks: BackgroundTasks,
) -> CreateFileResponse:
    """Create a new Google file (spreadsheet or document) and return join link."""
    user_token_data, _token = user_data
    file_id = None

    try:
        logger.info(
            f"Creating file | user_id={user_token_data.innohassle_id} "
            f"email={user_token_data.email} type={request.file_type} "
            f"title='{request.title}' role={request.user_role}"
        )

        file_id = create_google_file(file_type=request.file_type, title=request.title)

        file = await google_file_repository.create_file(
            author_id=get_user_id_from_token(user_token_data),
            user_role=request.user_role,
            file_id=file_id,
            file_type=request.file_type,
            title=request.title,
        )

        join_link = generate_join_link(file.slug)

        if request.file_type == "spreadsheet":
            background_tasks.add_task(
                setup_greeting_sheet,
                sheets_service=sheets_service(),
                spreadsheet_id=file_id,
                join_link=join_link,
                respondent_role=request.user_role,
            )

        return CreateFileResponse(
            file_id=file_id,
            file_type=request.file_type,
            title=request.title,
            user_role=request.user_role,
            join_link=join_link,
        )
    except HttpError as e:
        if file_id:
            delete_google_file(file_id)
        logger.error(f"Google API error: {e}")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        if file_id:
            delete_google_file(file_id)
        logger.error(f"Create file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/transfer")
async def transfer_file(
    request: TransferFileRequest,
    user_data: VerifyTokenDep,
) -> TransferFileResponse:
    """Accept ownership invitation for existing file, add it to system, cleanup public access, lock editors' sharing."""
    user_token_data, _token = user_data
    try:
        accepted = accept_ownership_if_pending(request.file_id)
        if not accepted:
            raise HTTPException(status_code=400, detail="Ownership invitation not found for this file")

        remove_public_links_and_lock_sharing(request.file_id)

        from src.modules.google_.service import drive_service

        drive = drive_service()
        meta = drive.files().get(fileId=request.file_id, fields="name, mimeType").execute()
        title = meta.get("name")
        mime = meta.get("mimeType", "")
        if "spreadsheet" in mime:
            file_type = "spreadsheet"
        elif "document" in mime:
            file_type = "document"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported mimeType: {mime}")

        file = await google_file_repository.create_file(
            author_id=get_user_id_from_token(user_token_data),
            user_role=request.user_role,
            file_id=request.file_id,
            file_type=file_type,  # type: ignore[arg-type]
            title=title,
        )

        join_link = generate_join_link(file.slug)

        users_count = count_user_permissions(request.file_id)
        cleanup_recommended = users_count > 2

        return TransferFileResponse(
            file_id=request.file_id,
            file_type=file_type,  # type: ignore[arg-type]
            title=title,
            user_role=request.user_role,
            join_link=join_link,
            cleanup_recommended=cleanup_recommended,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transfer file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{slug}")
async def delete_file(
    slug: str,
    user_data: VerifyTokenDep,
) -> DeleteFileResponse:
    """Delete a file by slug (author only)."""
    user_token_data, _token = user_data
    try:
        file = await google_file_repository.get_by_slug(slug)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        verify_file_ownership(file, user_token_data.innohassle_id)

        deleted = await google_file_repository.delete_by_slug(slug)
        if not deleted:
            raise HTTPException(status_code=404, detail="File not found")
        return DeleteFileResponse(message="File deleted")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file | slug={slug} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files")
async def get_files(
    user_data: VerifyTokenDep,
) -> list[GoogleFile]:
    """Get all files for the user (brief info without joins and banned)."""
    user_token_data, _token = user_data
    try:
        files = await google_file_repository.get_by_author_id(user_token_data.innohassle_id)
        return [
            GoogleFile(
                author_id=file.author_id,
                user_role=file.user_role,
                slug=file.slug,
                file_id=file.file_id,
                file_type=file.file_type,
                title=file.title,
                expire_at=file.expire_at,
                sso_joins_count=len(file.sso_joins or []),
                sso_banned_count=len(file.sso_banned or []),
                created_at=file.id.generation_time,
            )
            for file in files
        ]
    except Exception as e:
        logger.error(f"Error getting files | user_id={user_token_data.innohassle_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{slug}")
async def get_file(
    slug: str,
    user_data: VerifyTokenDep,
) -> GoogleFile:
    """Get full file information including joins and banned users."""
    user_token_data, _token = user_data
    try:
        file = await google_file_repository.get_by_slug(slug)

        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        verify_file_ownership(file, user_token_data.innohassle_id)

        return GoogleFile(
            author_id=file.author_id,
            user_role=file.user_role,
            slug=file.slug,
            file_id=file.file_id,
            file_type=file.file_type,
            title=file.title,
            expire_at=file.expire_at,
            sso_joins=[
                GoogleFileSSOJoinInfo(
                    user_id=join.user_id,
                    gmail=join.gmail,
                    innomail=join.innomail,
                    joined_at=join.joined_at,
                )
                for join in file.sso_joins
            ],
            sso_banned=[
                GoogleFileSSOBanInfo(
                    user_id=ban.user_id,
                    gmail=ban.gmail,
                    innomail=ban.innomail,
                    banned_at=ban.banned_at,
                )
                for ban in file.sso_banned
            ],
            sso_joins_count=len(file.sso_joins or []),
            sso_banned_count=len(file.sso_banned or []),
            created_at=file.id.generation_time,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file | slug={slug} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/{slug}/joins")
async def join_file(
    slug: str,
    request: JoinFileRequest,
    user_data: VerifyTokenDep,
) -> JoinFileResponse:
    """Add user to the file with specified role."""
    user_token_data, _token = user_data

    try:
        logger.info(
            f"Joining file | user_id={user_token_data.innohassle_id} "
            f"innomail={user_token_data.email} gmail={request.gmail} slug={slug}"
        )

        file = await add_user_to_file(
            file_slug=slug,
            user_id=get_user_id_from_token(user_token_data),
            gmail=request.gmail,
            innomail=user_token_data.email,
        )

        logger.info(
            f"File joined successfully | user_id={user_token_data.innohassle_id} "
            f"gmail={request.gmail} file_id={file.file_id}"
        )

        return JoinFileResponse(
            message=f"Successfully added {request.gmail}",
            file_id=file.file_id,
        )

    except HttpError as e:
        logger.error(
            f"Google API error | user_id={user_token_data.innohassle_id} gmail={request.gmail} slug={slug} error={e}"
        )
        if e.resp.status == 403:
            raise HTTPException(
                status_code=403,
                detail="Permission denied. Make sure the service account has access to the file.",
            )
        if e.resp.status == 404:
            raise HTTPException(status_code=404, detail="File not found.")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except UserBannedException as e:
        logger.error(f"User banned: {e}")
        raise HTTPException(status_code=403, detail="Permission denied. You are banned from this file.")
    except InvalidGmailException as e:
        logger.error(f"Invalid gmail: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Gmail {e.gmail} does not exist or is not associated with a Google account",
        )
    except Exception as e:
        logger.error(
            f"Error joining file | user_id={user_token_data.innohassle_id} gmail={request.gmail} slug={slug} error={e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/{slug}/bans")
async def ban_user(
    slug: str,
    request: BanUserRequest,
    user_data: VerifyTokenDep,
) -> BanUserResponse:
    """Ban user from the file."""
    user_token_data, _token = user_data

    try:
        file = await google_file_repository.get_by_slug(slug)

        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        verify_file_ownership(file, user_token_data.innohassle_id)

        joins_to_ban = [join for join in file.sso_joins if join.user_id == request.user_id]

        if not joins_to_ban:
            raise HTTPException(status_code=404, detail=f"User with user_id {request.user_id} not found in joins")

        for join_to_ban in joins_to_ban:
            logger.info(
                f"Banning user | author_id={user_token_data.innohassle_id} "
                f"banned_user_id={join_to_ban.user_id} gmail={join_to_ban.gmail} slug={slug}"
            )

            if join_to_ban.permission_id:
                revoke_file_permission(file.file_id, join_to_ban.permission_id)

            await google_file_repository.ban_user_from_file(
                slug=slug,
                user_id=join_to_ban.user_id,
                gmail=join_to_ban.gmail,
                innomail=join_to_ban.innomail,
            )

        logger.info(
            f"User banned successfully | banned_user_id={join_to_ban.user_id} gmail={join_to_ban.gmail} slug={slug}"
        )

        return BanUserResponse(
            message=f"Successfully banned {join_to_ban.user_id}",
        )

    except HTTPException:
        raise
    except HttpError as e:
        logger.error(f"Google API error while banning user: {e}")
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        logger.error(f"Error banning user | slug={slug} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{slug}/bans/{user_id}")
async def unban_user(
    slug: str,
    user_id: str,
    user_data: VerifyTokenDep,
) -> UnbanUserResponse:
    """Unban user by user_id (author only)."""
    user_token_data, _token = user_data
    try:
        file = await google_file_repository.get_by_slug(slug)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        verify_file_ownership(file, user_token_data.innohassle_id)

        try:
            user_oid = PydanticObjectId(user_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid user_id")

        await google_file_repository.unban_user_from_file(slug=slug, user_id=user_oid)
        return UnbanUserResponse(message=f"Successfully unbanned {user_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unbanning user | slug={slug} user_id={user_id} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/{slug}/cleanup")
async def cleanup_file_permissions(
    slug: str,
    user_data: VerifyTokenDep,
) -> CleanupResponse:
    """Remove any user permissions that are not present in sso_joins."""
    user_token_data, _token = user_data
    try:
        file = await google_file_repository.get_by_slug(slug)
        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        verify_file_ownership(file, user_token_data.innohassle_id)

        from src.modules.google_.service import drive_service

        drive = drive_service()
        perms = drive.permissions().list(fileId=file.file_id, fields="permissions(id,type,emailAddress)").execute()

        allowed_emails = {j.gmail for j in file.sso_joins}
        removed = 0
        for p in perms.get("permissions", []):
            if p.get("type") != "user":
                continue
            email = p.get("emailAddress")
            if not email:
                continue
            if email not in allowed_emails:
                try:
                    drive.permissions().delete(fileId=file.file_id, permissionId=p["id"]).execute()
                    removed += 1
                except Exception as e:
                    logger.error(f"Error removing permission {p['id']} from {email}: {e}")

        return CleanupResponse(removed=removed)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cleanup file permissions error for {slug}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
