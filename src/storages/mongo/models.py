from datetime import datetime
from typing import Literal

from beanie import PydanticObjectId
from pydantic import BaseModel

from src.storages.mongo.__base__ import CustomDocument

type UserID = PydanticObjectId


class GoogleLinkJoin(BaseModel):
    user_id: UserID
    gmail: str
    innomail: str
    joined_at: datetime
    permission_id: str | None = None


type GoogleLinkUserRole = Literal["writer", "reader"]


class GoogleLinkSchema(BaseModel):
    author_id: UserID
    user_role: GoogleLinkUserRole
    slug: str
    spreadsheet_id: str
    title: str | None = None
    expire_at: datetime | None = None
    joins: list[GoogleLinkJoin]
    banned: list[UserID]


class GoogleLink(GoogleLinkSchema, CustomDocument):
    pass


document_models = [GoogleLink]
