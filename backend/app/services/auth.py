from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, ExpiredSignatureError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import RefreshToken, User
from ..utils.database import get_db
from ..utils.logger import logger
from ..utils.redis_client import redis_client

# Use pbkdf2_sha256 to avoid bcrypt backend compatibility issues
# and the 72-byte bcrypt password limit.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer()


class AuthManager:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(user_id: int) -> str:
        payload = {
            "user_id": user_id,
            "type": "access",
            "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def create_refresh_token(user_id: int) -> str:
        payload = {
            "user_id": user_id,
            "type": "refresh",
            "exp": datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> dict:
        try:
            return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    @staticmethod
    async def verify_access_token(token: str, session: AsyncSession) -> User:
        if await redis_client.exists(f"blacklist:{token}"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

        payload = AuthManager.decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user_id in token")

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        return user

    @staticmethod
    async def verify_refresh_token(token: str, session: AsyncSession) -> User:
        if await redis_client.exists(f"blacklist:{token}"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

        payload = AuthManager.decode_token(token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user_id in token")

        result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.token == token,
                RefreshToken.user_id == user_id,
                RefreshToken.revoked.is_(False),
            )
        )
        refresh_token = result.scalar_one_or_none()
        if not refresh_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalid")

        if refresh_token.expires_at < datetime.utcnow():
            refresh_token.revoked = True
            refresh_token.revoked_at = datetime.utcnow()
            await session.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        return user

    @staticmethod
    async def create_refresh_token_record(user_id: int, token: str, session: AsyncSession) -> RefreshToken:
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        session.add(refresh_token)
        await session.commit()
        await session.refresh(refresh_token)
        return refresh_token

    @staticmethod
    async def revoke_token(token: str, session: Optional[AsyncSession] = None) -> None:
        await redis_client.set(f"blacklist:{token}", "1", expire=settings.REDIS_TOKEN_TTL)

        if session:
            result = await session.execute(select(RefreshToken).where(RefreshToken.token == token))
            refresh_token = result.scalar_one_or_none()
            if refresh_token:
                refresh_token.revoked = True
                refresh_token.revoked_at = datetime.utcnow()
                await session.commit()

    @staticmethod
    async def refresh_tokens(refresh_token: str, session: AsyncSession) -> Tuple[str, str]:
        user = await AuthManager.verify_refresh_token(refresh_token, session)

        await AuthManager.revoke_token(refresh_token, session)

        new_access_token = AuthManager.create_access_token(user.id)
        new_refresh_token = AuthManager.create_refresh_token(user.id)
        await AuthManager.create_refresh_token_record(user.id, new_refresh_token, session)

        logger.info(f"User {user.username} refreshed token")
        return new_access_token, new_refresh_token

    @staticmethod
    async def logout(access_token: str, refresh_token: Optional[str] = None, session: Optional[AsyncSession] = None) -> None:
        await AuthManager.revoke_token(access_token, session)
        if refresh_token:
            await AuthManager.revoke_token(refresh_token, session)

        logger.info("User logged out")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    return await AuthManager.verify_access_token(token, session)
