from datetime import datetime
from typing import Literal

from beanie import PydanticObjectId
from pydantic import BaseModel

Role = Literal["writer", "reader"]


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
    title: str | None = None
    "Optional title for the document"


class SetupSpreadsheetResponse(BaseModel):
    sheet_title: str
    "Title of the created sheet"
    spreadsheet_id: str
    "Spreadsheet ID"
    role_display: str
    "Role display name"
    join_link: str
    "Join link for respondents"


class GoogleLinkJoinInfo(BaseModel):
    user_id: PydanticObjectId
    "User ID"
    gmail: str
    "Gmail address"
    innomail: str
    "Innopolis email"
    joined_at: datetime
    "Date and time when user joined"


class GoogleLinkBanInfo(BaseModel):
    user_id: PydanticObjectId
    "User ID"
    gmail: str
    "Gmail address"
    innomail: str
    "Innopolis email"
    banned_at: datetime
    "Date and time when user was banned"


class GoogleLink(BaseModel):
    author_id: PydanticObjectId
    "Author ID"
    user_role: Role
    "Role for users (writer or reader)"
    slug: str
    "Unique slug for the link"
    spreadsheet_id: str
    "Google Spreadsheet ID"
    title: str | None = None
    "Document title"
    expire_at: datetime | None = None
    "Expiration date"
    joins: list[GoogleLinkJoinInfo] | None = None
    "List of users who joined"
    joins_count: int
    "Count of joins"
    banned: list[GoogleLinkBanInfo] | None = None
    "List of banned users"
    banned_count: int
    "Count of banned users"
    created_at: datetime
    "Date and time when document was created"


class JoinDocumentResponse(BaseModel):
    message: str
    "Message"
    spreadsheet_id: str
    "Spreadsheet ID"


class BanUserRequest(BaseModel):
    user_id: PydanticObjectId
    "User ID to ban"


class BanUserResponse(BaseModel):
    message: str
    "Message"
