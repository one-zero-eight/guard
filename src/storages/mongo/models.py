from datetime import datetime
from typing import Literal

from beanie import PydanticObjectId
from pydantic import BaseModel

from src.storages.mongo.__base__ import CustomDocument

type UserID = PydanticObjectId

type GoogleFileUserRole = Literal["writer", "reader"]
type GoogleFileType = Literal["spreadsheet", "document"]


class GoogleFileSSOJoin(BaseModel):
    user_id: UserID
    gmail: str
    innomail: str
    role: GoogleFileUserRole
    joined_at: datetime
    permission_id: str


class GoogleFileSSOBan(BaseModel):
    user_id: UserID
    gmail: str
    innomail: str
    banned_at: datetime


class GoogleFileSchema(BaseModel):
    author_id: UserID
    default_role: GoogleFileUserRole
    owner_gmail: str
    owner_permission_id: str
    slug: str
    file_id: str
    file_type: GoogleFileType
    title: str
    expire_at: datetime | None = None
    sso_joins: list[GoogleFileSSOJoin]
    sso_banned: list[GoogleFileSSOBan]


class GoogleFile(GoogleFileSchema, CustomDocument):
    pass


document_models = [GoogleFile]
