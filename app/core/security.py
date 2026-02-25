"""Security helpers — validates Supabase-issued JWTs and resolves the current user."""

import logging

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.models.user import Profile

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# JWKS client fetches and caches Supabase's public keys for ES256 verification
_jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
_jwks_client = PyJWKClient(_jwks_url)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Profile:
    """Decode a Supabase JWT and return the corresponding Profile row."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Get the signing key from Supabase JWKS using the token's 'kid' header
        signing_key = _jwks_client.get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            options={"verify_aud": False},
            leeway=30,  # allow 30s clock skew between local machine and Supabase
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            logger.warning("JWT decoded but 'sub' claim is missing")
            raise credentials_exception
    except jwt.PyJWTError as e:
        logger.warning("JWT decode failed: %s", e)
        raise credentials_exception

    profile = db.query(Profile).filter(Profile.id == user_id).first()
    if profile is None:
        logger.warning("No profile found for user_id=%s", user_id)
        raise credentials_exception
    return profile
