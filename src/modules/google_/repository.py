import random
from datetime import datetime
from string import ascii_letters, digits

from src.storages.mongo.models import GoogleLink, GoogleLinkJoin, GoogleLinkUserRole, UserID


def generate_slug():
    return "".join(random.choices(ascii_letters + digits, k=10))


class GoogleLinkRepository:
    async def setup_spreadsheet(
        self, author_id: UserID, user_role: GoogleLinkUserRole, spreadsheet_id: str
    ) -> GoogleLink:
        link = GoogleLink(
            author_id=author_id,
            user_role=user_role,
            spreadsheet_id=spreadsheet_id,
            slug=generate_slug(),
            joins=[],
            banned=[],
        )
        await link.save()
        return link

    async def get_by_slug(self, slug: str) -> GoogleLink | None:
        return await GoogleLink.find_one(GoogleLink.slug == slug)

    async def get_by_author_id(self, author_id: UserID) -> list[GoogleLink]:
        return await GoogleLink.find(GoogleLink.author_id == author_id).to_list()

    async def get_joins(self, slug: str) -> list[GoogleLinkJoin]:
        return await GoogleLink.find_one(GoogleLink.slug == slug).joins

    async def add_join(self, slug: str, user_id: UserID, gmail: str, innomail: str):
        link = await self.get_by_slug(slug)
        if link:
            link.joins.append(GoogleLinkJoin(user_id=user_id, gmail=gmail, innomail=innomail, joined_at=datetime.now()))
            await link.save()
            return link
        return None

    async def search_joins(self, slug: str, query: str) -> list[GoogleLinkJoin]:
        link = await self.get_by_slug(slug)
        if link:
            return [join for join in link.joins if query in join.gmail or query in join.innomail]
        return []

    async def add_banned(self, slug: str, user_id: UserID):
        link = await self.get_by_slug(slug)
        if link:
            link.banned.append(user_id)
            await link.save()
            return link
        return None

    async def remove_banned(self, slug: str, user_id: UserID):
        link = await self.get_by_slug(slug)
        if link:
            link.banned.remove(user_id)
            await link.save()
            return link
        return None

    async def get_banned(self, slug: str) -> list[UserID]:
        return await GoogleLink.find_one(GoogleLink.slug == slug).banned


google_link_repository = GoogleLinkRepository()
