import random
from datetime import datetime
from string import ascii_letters, digits

from beanie import PydanticObjectId

from src.modules.google_.constants import SLUG_LENGTH
from src.modules.google_.exceptions import UserBannedException
from src.storages.mongo.models import (
    GoogleFile,
    GoogleFileSSOBan,
    GoogleFileSSOJoin,
    GoogleFileType,
    GoogleFileUserRole,
    UserID,
)


def generate_slug():
    return "".join(random.choices(ascii_letters + digits, k=SLUG_LENGTH))


class GoogleFileRepository:
    async def create_file(
        self,
        author_id: UserID,
        user_role: GoogleFileUserRole,
        file_id: str,
        file_type: GoogleFileType,
        title: str,
    ) -> GoogleFile:
        file = GoogleFile(
            author_id=author_id,
            user_role=user_role,
            file_id=file_id,
            file_type=file_type,
            slug=generate_slug(),
            title=title,
            sso_joins=[],
            sso_banned=[],
        )
        await file.save()
        return file

    async def get_by_file_id(self, file_id: str) -> GoogleFile | None:
        return await GoogleFile.find_one(GoogleFile.file_id == file_id)

    async def get_by_slug(self, slug: str) -> GoogleFile | None:
        return await GoogleFile.find_one(GoogleFile.slug == slug)

    async def get_by_author_id(self, author_id: str) -> list[GoogleFile]:
        return await GoogleFile.find(GoogleFile.author_id == PydanticObjectId(author_id)).to_list()

    async def join_user_to_file(
        self, slug: str, user_id: UserID, gmail: str, innomail: str, permission_id: str | None = None
    ):
        file = await self.get_by_slug(slug)
        if not file:
            return None

        if any(join.gmail == gmail for join in file.sso_joins):
            return file

        if any(ban.user_id == user_id for ban in file.sso_banned):
            raise UserBannedException(user_id=user_id)

        file.sso_joins.append(
            GoogleFileSSOJoin(
                user_id=user_id,
                gmail=gmail,
                innomail=innomail,
                joined_at=datetime.now(),
                permission_id=permission_id,
            )
        )
        await file.save()
        return file

    async def ban_user_from_file(self, slug: str, user_id: UserID, gmail: str, innomail: str):
        file = await self.get_by_slug(slug)
        if not file:
            return None

        file.sso_joins = [j for j in file.sso_joins if j.user_id != user_id]

        if any(ban.user_id == user_id for ban in file.sso_banned):
            await file.save()
            return file

        file.sso_banned.append(
            GoogleFileSSOBan(
                user_id=user_id,
                gmail=gmail,
                innomail=innomail,
                banned_at=datetime.now(),
            )
        )
        await file.save()
        return file

    async def unban_user_from_file(self, slug: str, user_id: UserID):
        file = await self.get_by_slug(slug)
        if not file:
            return None

        if not any(ban.user_id == user_id for ban in file.sso_banned):
            return file

        file.sso_banned = [ban for ban in file.sso_banned if ban.user_id != user_id]
        await file.save()
        return file

    async def delete_by_slug(self, slug: str) -> bool:
        file = await self.get_by_slug(slug)
        if not file:
            return False
        await file.delete()
        return True


google_file_repository = GoogleFileRepository()
