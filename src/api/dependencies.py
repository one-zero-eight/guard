__all__ = ["VerifyTokenDep", "verify_token_dep"]

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.modules.inh_accounts_sdk import UserTokenData, inh_accounts

bearer_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="Token from [InNoHassle Accounts](https://innohassle.ru/account/token)",
    bearerFormat="JWT",
    auto_error=False,  # We'll handle error manually
)


async def verify_token_dep(
    bearer: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> tuple[UserTokenData, str] | None:
    # Prefer header to cookie
    token = bearer and bearer.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No credentials provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = inh_accounts.decode_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data, token


VerifyTokenDep = Annotated[tuple[UserTokenData, str], Depends(verify_token_dep)]
"""
Dependency for verifying the user token.
"""
