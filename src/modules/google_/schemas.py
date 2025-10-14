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


class GoogleLink(BaseModel):
    author_id: PydanticObjectId
    "Author ID"
    user_role: Role
    "Role for users (writer or reader)"
    slug: str
    "Unique slug for the link"
    spreadsheet_id: str
    "Google Spreadsheet ID"
    expire_at: datetime | None = None
    "Expiration date"
    joins: list[GoogleLinkJoinInfo]
    "List of users who joined"
    banned: list[PydanticObjectId]
    "List of banned user IDs"


class JoinDocumentResponse(BaseModel):
    message: str
    "Message"
    spreadsheet_id: str
    "Spreadsheet ID"
