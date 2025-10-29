"""
JWT Manager for Python services
"""

import os
from datetime import datetime, timedelta

import jwt  # type: ignore[import]
from pydantic import BaseModel  # type: ignore[import]


class TokenClaims(BaseModel):
    """JWT token claims"""

    user_id: str
    username: str
    email: str
    roles: list[str]
    exp: int
    iat: int
    iss: str = "voice-assistant"
    sub: str


class JWTManager:
    """JWT token manager"""

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_expiry: int = 3600,  # 1 hour
        refresh_expiry: int = 604800,  # 7 days
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_expiry = access_expiry
        self.refresh_expiry = refresh_expiry

    def generate_access_token(
        self, user_id: str, username: str, email: str, roles: list[str]
    ) -> str:
        """Generate an access token"""
        now = datetime.utcnow()
        exp = now + timedelta(seconds=self.access_expiry)

        payload = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "roles": roles,
            "exp": int(exp.timestamp()),
            "iat": int(now.timestamp()),
            "iss": "voice-assistant",
            "sub": user_id,
        }

        token: str = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token

    def generate_refresh_token(self, user_id: str) -> str:
        """Generate a refresh token"""
        now = datetime.utcnow()
        exp = now + timedelta(seconds=self.refresh_expiry)

        payload = {
            "sub": user_id,
            "exp": int(exp.timestamp()),
            "iat": int(now.timestamp()),
            "iss": "voice-assistant",
        }

        token: str = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token

    def validate_token(self, token: str) -> TokenClaims | None:
        """Validate a token and return claims"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return TokenClaims(**payload)
        except jwt.ExpiredSignatureError as err:
            raise ValueError("Token expired") from err
        except jwt.InvalidTokenError as err:
            raise ValueError("Invalid token") from err

    def refresh_access_token(
        self,
        refresh_token: str,
        username: str,
        email: str,
        roles: list[str],
    ) -> str:
        """Refresh an access token using a refresh token"""
        try:
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=[self.algorithm])
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError("Invalid refresh token")

            return self.generate_access_token(user_id, username, email, roles)
        except jwt.ExpiredSignatureError as err:
            raise ValueError("Refresh token expired") from err
        except jwt.InvalidTokenError as err:
            raise ValueError("Invalid refresh token") from err


# Global JWT manager instance
_jwt_manager: JWTManager | None = None


def get_jwt_manager() -> JWTManager:
    """Get the global JWT manager instance"""
    global _jwt_manager
    if _jwt_manager is None:
        secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
        _jwt_manager = JWTManager(secret_key)
    return _jwt_manager
