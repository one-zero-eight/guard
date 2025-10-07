from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.modules.inh_accounts_sdk import inh_accounts


@asynccontextmanager
async def lifespan(app: FastAPI):
    await inh_accounts.update_key_set()
    yield
