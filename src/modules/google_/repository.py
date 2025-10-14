import random
from datetime import datetime
from string import ascii_letters, digits

from beanie import PydanticObjectId

from src.modules.google_.exceptions import UserAlreadyJoinedExceptionWithAnotherGmail, UserBannedException
from src.storages.mongo.models import GoogleLink, GoogleLinkBan, GoogleLinkJoin, GoogleLinkUserRole, UserID


def generate_slug():
    return "".join(random.choices(ascii_letters + digits, k=10))


def is_user_banned(
    banned: list[GoogleLinkBan],
    user_id: PydanticObjectId | None = None,
    innomail: str | None = None,
    gmail: str | None = None,
) -> bool:
    for ban in banned:
        if user_id and ban.user_id == user_id:
            return True
        if innomail and ban.innomail == innomail:
            return True
        if gmail and ban.gmail == gmail:
            return True
    return False


class GoogleLinkRepository:
    async def setup_spreadsheet(
        self, author_id: UserID, user_role: GoogleLinkUserRole, spreadsheet_id: str, title: str | None = None
    ) -> GoogleLink:
        link = GoogleLink(
            author_id=author_id,
            user_role=user_role,
            spreadsheet_id=spreadsheet_id,
            slug=generate_slug(),
            title=title,
            joins=[],
            banned=[],
        )
        await link.save()
        return link

    async def get_by_spreadsheet_id(self, spreadsheet_id: str) -> GoogleLink | None:
        return await GoogleLink.find_one(GoogleLink.spreadsheet_id == spreadsheet_id)

    async def get_by_slug(self, slug: str) -> GoogleLink | None:
        return await GoogleLink.find_one(GoogleLink.slug == slug)

    async def get_by_author_id(self, author_id: str) -> list[GoogleLink]:
        return await GoogleLink.find(GoogleLink.author_id == PydanticObjectId(author_id)).to_list()

    async def add_join(self, slug: str, user_id: UserID, gmail: str, innomail: str, permission_id: str | None = None):
        link = await self.get_by_slug(slug)
        if link:
            if any(join.gmail == gmail for join in link.joins):
                return link
            if any(str(join.user_id) == str(user_id) for join in link.joins):
                raise UserAlreadyJoinedExceptionWithAnotherGmail(user_id=user_id)
            if is_user_banned(banned=link.banned, user_id=user_id, innomail=innomail, gmail=gmail):
                raise UserBannedException(user_id=user_id)
            link.joins.append(
                GoogleLinkJoin(
                    user_id=user_id,
                    gmail=gmail,
                    innomail=innomail,
                    joined_at=datetime.now(),
                    permission_id=permission_id,
                )
            )
            await link.save()
            return link
        return None

    async def add_banned(self, slug: str, user_id: UserID, gmail: str, innomail: str):
        link = await self.get_by_slug(slug)
        if link:
            link.joins = [j for j in link.joins if j.user_id != user_id]
            if any(ban.user_id == user_id for ban in link.banned):
                await link.save()
                return link
            link.banned.append(
                GoogleLinkBan(
                    user_id=user_id,
                    gmail=gmail,
                    innomail=innomail,
                    banned_at=datetime.now(),
                )
            )
            await link.save()
            return link
        return None

    async def remove_banned(self, slug: str, user_id: UserID):
        link = await self.get_by_slug(slug)
        if link:
            if not any(ban.user_id == user_id for ban in link.banned):
                return link
            link.banned = [ban for ban in link.banned if ban.user_id != user_id]
            await link.save()
            return link
        return None

    async def delete_by_slug(self, slug: str) -> bool:
        link = await self.get_by_slug(slug)
        if not link:
            return False
        await link.delete()
        return True


google_link_repository = GoogleLinkRepository()
