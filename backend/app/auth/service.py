"""
ForecastIQ Authentication Business Logic & Service Layer
Handles user registration, authentication verification, session issuance, and user lookup.
"""
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
import logging
import uuid
from pymongo.errors import DuplicateKeyError, PyMongoError

from ..db.mongo import MongoRepository, MongoManager
from ..config.settings import settings
from .schemas import UserRegisterRequest, UserLoginRequest, UserSafeResponse
from .security import hash_password, verify_password, generate_session_token, hash_session_token

logger = logging.getLogger(__name__)


class AuthService:
    """Service handling MongoDB-backed user authentication and sessions."""

    @classmethod
    def register_user(cls, req: UserRegisterRequest) -> Tuple[bool, str, Optional[UserSafeResponse], Optional[str]]:
        """
        Register a new user in MongoDB.
        Returns: (success: bool, message: str, user: Optional[UserSafeResponse], session_token: Optional[str])
        """
        normalized_email = req.email.strip().lower()

        # Check MongoDB connectivity
        if not MongoManager.is_connected() and MongoManager.get_db() is None:
            return False, "Database connection unavailable. Please check that MongoDB is online.", None, None

        # Check existing user
        try:
            existing = MongoRepository.get_user_by_email(normalized_email)
            if existing:
                return False, "An account with this email address already exists.", None, None
        except Exception as e:
            logger.error(f"Error checking existing user in MongoDB: {e}")
            return False, "Database error verifying existing user.", None, None

        # Hash password and create user doc
        pwd_hash = hash_password(req.password)
        user_id = str(uuid.uuid4())
        now = datetime.utcnow()

        user_doc = {
            "user_id": user_id,
            "full_name": req.full_name.strip(),
            "email": normalized_email,
            "password_hash": pwd_hash,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
        }

        try:
            created = MongoRepository.create_user(user_doc)
        except DuplicateKeyError:
            return False, "An account with this email address already exists.", None, None
        except Exception as e:
            logger.error(f"Error inserting user into MongoDB: {e}")
            return False, f"Failed to create user account: {str(e)}", None, None

        # Create session automatically for convenient onboarding
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        expires_at = datetime.utcnow() + timedelta(hours=settings.AUTH_SESSION_TTL_HOURS)

        try:
            MongoRepository.create_session(
                session_token_hash=token_hash,
                user_id=user_id,
                email=normalized_email,
                expires_at=expires_at
            )
        except Exception as e:
            logger.warning(f"Could not establish initial session for newly registered user: {e}")
            raw_token = None

        safe_user = UserSafeResponse(
            user_id=user_id,
            full_name=user_doc["full_name"],
            email=user_doc["email"],
            created_at=user_doc.get("created_at"),
            is_active=user_doc.get("is_active", True)
        )

        return True, "Registration successful.", safe_user, raw_token

    @classmethod
    def login_user(cls, req: UserLoginRequest) -> Tuple[bool, str, Optional[UserSafeResponse], Optional[str]]:
        """
        Authenticate user credentials against MongoDB and issue a session.
        Returns: (success: bool, message: str, user: Optional[UserSafeResponse], session_token: Optional[str])
        """
        normalized_email = req.email.strip().lower()

        if not MongoManager.is_connected() and MongoManager.get_db() is None:
            return False, "Database connection unavailable. Please check that MongoDB is online.", None, None

        try:
            user = MongoRepository.get_user_by_email(normalized_email)
        except Exception as e:
            logger.error(f"Database error during login: {e}")
            return False, "Database error retrieving user profile.", None, None

        # Generic message to avoid email enumeration
        if not user or not user.get("is_active", True):
            return False, "Invalid email or password.", None, None

        if not verify_password(req.password, user.get("password_hash", "")):
            return False, "Invalid email or password.", None, None

        # Create session
        user_id = user.get("user_id") or str(user["_id"])
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        expires_at = datetime.utcnow() + timedelta(hours=settings.AUTH_SESSION_TTL_HOURS)

        try:
            MongoRepository.create_session(
                session_token_hash=token_hash,
                user_id=user_id,
                email=normalized_email,
                expires_at=expires_at
            )
        except Exception as e:
            logger.error(f"Failed to save session to MongoDB: {e}")
            return False, "Could not establish secure session on database.", None, None

        safe_user = UserSafeResponse(
            user_id=user_id,
            full_name=user["full_name"],
            email=user["email"],
            created_at=user.get("created_at"),
            is_active=user.get("is_active", True)
        )

        return True, "Login successful.", safe_user, raw_token

    @classmethod
    def get_current_user(cls, raw_token: Optional[str]) -> Optional[UserSafeResponse]:
        """Validate session token and return user profile if session is active."""
        if not raw_token:
            return None

        if not MongoManager.is_connected() and MongoManager.get_db() is None:
            return None

        token_hash = hash_session_token(raw_token)
        try:
            session = MongoRepository.get_session(token_hash)
            if not session:
                return None

            user_id = session.get("user_id")
            user = MongoRepository.get_user_by_id(user_id)
            if not user or not user.get("is_active", True):
                return None

            return UserSafeResponse(
                user_id=user.get("user_id") or str(user["_id"]),
                full_name=user["full_name"],
                email=user["email"],
                created_at=user.get("created_at"),
                is_active=user.get("is_active", True)
            )
        except Exception as e:
            logger.error(f"Error verifying session: {e}")
            return None

    @classmethod
    def logout_user(cls, raw_token: Optional[str]) -> bool:
        """Invalidate session in MongoDB."""
        if not raw_token:
            return True

        if not MongoManager.is_connected() and MongoManager.get_db() is None:
            return False

        try:
            token_hash = hash_session_token(raw_token)
            MongoRepository.delete_session(token_hash)
            return True
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False
