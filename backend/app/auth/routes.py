"""
ForecastIQ Authentication API Routes
Provides endpoints for:
- POST /api/auth/register
- POST /api/auth/login
- GET  /api/auth/me
- POST /api/auth/logout
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Response, Request, status, Cookie
from .schemas import UserRegisterRequest, UserLoginRequest, UserSafeResponse, AuthResponse
from .service import AuthService
from ..config.settings import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_auth_cookie(response: Response, token: str):
    """Attach secure, HttpOnly session cookie to the response."""
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        max_age=settings.AUTH_SESSION_TTL_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.AUTH_COOKIE_SECURE,
        path="/"
    )


def _clear_auth_cookie(response: Response):
    """Clear session cookie from the client."""
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.AUTH_COOKIE_SECURE
    )


def _extract_token(request: Request, cookie_token: Optional[str] = None) -> Optional[str]:
    """Extract session token from HttpOnly cookie or Authorization Bearer header."""
    if cookie_token:
        return cookie_token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return None


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(req: UserRegisterRequest, response: Response):
    """Register a new user in MongoDB and establish initial session."""
    success, message, user, token = AuthService.register_user(req)
    if not success:
        if "already exists" in message.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
        if "database" in message.lower() or "connection" in message.lower():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    if token:
        _set_auth_cookie(response, token)

    return AuthResponse(
        success=True,
        message=message,
        user=user,
        session_token=token
    )


@router.post("/login", response_model=AuthResponse)
def login(req: UserLoginRequest, response: Response):
    """Authenticate email and password against MongoDB and issue a session."""
    success, message, user, token = AuthService.login_user(req)
    if not success:
        if "database" in message.lower() or "connection" in message.lower():
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=message)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)

    if token:
        _set_auth_cookie(response, token)

    return AuthResponse(
        success=True,
        message=message,
        user=user,
        session_token=token
    )


@router.get("/me", response_model=UserSafeResponse)
def get_current_user(
    request: Request,
    forecastiq_session: Optional[str] = Cookie(None)
):
    """Retrieve the currently authenticated user's safe profile."""
    token = _extract_token(request, forecastiq_session)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials not provided or expired."
        )

    user = AuthService.get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or has expired."
        )

    return user


@router.post("/logout", response_model=AuthResponse)
def logout(
    request: Request,
    response: Response,
    forecastiq_session: Optional[str] = Cookie(None)
):
    """Invalidate session in MongoDB and clear client session cookie."""
    token = _extract_token(request, forecastiq_session)
    if token:
        AuthService.logout_user(token)

    _clear_auth_cookie(response)
    return AuthResponse(
        success=True,
        message="Logged out successfully."
    )
