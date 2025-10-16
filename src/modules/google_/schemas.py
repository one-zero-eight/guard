from datetime import datetime
from typing import Literal

from beanie import PydanticObjectId
from pydantic import BaseModel

Role = Literal["writer", "reader"]
FileType = Literal["spreadsheet", "document"]


class JoinFileRequest(BaseModel):
    gmail: str
    "Gmail address to add to the file"


class ServiceAccountEmailResponse(BaseModel):
    email: str
    "Service account email address"


class CreateFileRequest(BaseModel):
    file_type: FileType
    "Type of file to create (spreadsheet or document)"
    title: str
    "Title of the file"
    user_role: Role
    "Role for users (writer or reader)"


class CreateFileResponse(BaseModel):
    file_id: str
    "Google File ID"
    file_type: FileType
    "Type of file (spreadsheet or document)"
    title: str
    "Title of the file"
    user_role: Role
    "Role for users (writer or reader)"
    join_link: str
    "Join link for users"


class TransferFileRequest(BaseModel):
    file_id: str
    "Existing Google File ID to transfer into system"
    user_role: Role
    "Role for future respondents (writer or reader)"


class TransferFileResponse(BaseModel):
    file_id: str
    "Google File ID"
    file_type: FileType
    "Type of file (spreadsheet or document)"
    title: str
    "Title of the file"
    user_role: Role
    "Role for users (writer or reader)"
    join_link: str
    "Join link for users"
    cleanup_recommended: bool
    "True if more than 2 user permissions exist (owner + previous owner)"


class GoogleFileSSOJoinInfo(BaseModel):
    user_id: PydanticObjectId
    "User ID"
    gmail: str
    "Gmail address"
    innomail: str
    "Innopolis email"
    joined_at: datetime
    "Date and time when user joined"


class GoogleFileSSOBanInfo(BaseModel):
    user_id: PydanticObjectId
    "User ID"
    gmail: str
    "Gmail address"
    innomail: str
    "Innopolis email"
    banned_at: datetime
    "Date and time when user was banned"


class GoogleFile(BaseModel):
    author_id: PydanticObjectId
    "Author ID"
    user_role: Role
    "Role for users (writer or reader)"
    slug: str
    "Unique slug for the link"
    file_id: str
    "Google File ID"
    file_type: FileType
    "Type of file (spreadsheet or document)"
    title: str
    "File title"
    expire_at: datetime | None = None
    "Expiration date"
    sso_joins: list[GoogleFileSSOJoinInfo] | None = None
    "List of users who joined via SSO"
    sso_joins_count: int
    "Count of SSO joins"
    sso_banned: list[GoogleFileSSOBanInfo] | None = None
    "List of banned users"
    sso_banned_count: int
    "Count of banned users"
    created_at: datetime
    "Date and time when file was created"


class JoinFileResponse(BaseModel):
    message: str
    "Message"
    file_id: str
    "Google File ID"


class BanUserRequest(BaseModel):
    user_id: PydanticObjectId
    "User ID to ban"


class BanUserResponse(BaseModel):
    message: str
    "Message"


class CleanupResponse(BaseModel):
    removed: int
    "Number of permissions removed"


class DeleteFileResponse(BaseModel):
    message: str
    "Message"


class UnbanUserResponse(BaseModel):
    message: str
    "Message"


class HealthCheckResponse(BaseModel):
    status: str
    "Health status"
    service: str
    "Service name"
