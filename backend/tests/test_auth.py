import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
import bcrypt

from app.main import app
from app.auth.security import hash_password, verify_password, generate_session_token, hash_session_token
from app.auth.service import AuthService
from app.auth.schemas import UserRegisterRequest, UserLoginRequest

client = TestClient(app)

def test_password_hashing():
    raw_pwd = "MySecretPassword123!"
    hashed = hash_password(raw_pwd)
    assert hashed != raw_pwd
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(raw_pwd, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False

def test_session_token_hashing():
    token = generate_session_token()
    assert len(token) > 20
    hashed = hash_session_token(token)
    assert hashed != token
    assert hash_session_token(token) == hashed

def test_register_validation_errors():
    # Missing fields
    resp = client.post("/api/auth/register", json={})
    assert resp.status_code == 422

    # Invalid email
    resp = client.post("/api/auth/register", json={
        "full_name": "Test User",
        "email": "invalid-email-format",
        "password": "ValidPassword123"
    })
    assert resp.status_code == 422

    # Weak/short password (<6 chars)
    resp = client.post("/api/auth/register", json={
        "full_name": "Test User",
        "email": "test@example.com",
        "password": "123"
    })
    assert resp.status_code == 422

@patch("app.auth.service.MongoRepository")
def test_register_duplicate_email(mock_repo):
    mock_repo.get_user_by_email.return_value = {
        "_id": "mock_id",
        "email": "existing@example.com",
        "full_name": "Existing User"
    }

    resp = client.post("/api/auth/register", json={
        "full_name": "Existing User",
        "email": "existing@example.com",
        "password": "Password123!"
    })
    assert resp.status_code == 409
    data = resp.json()
    assert "already exists" in data["detail"].lower() or "already registered" in data["detail"].lower()

@patch("app.auth.service.MongoRepository")
def test_register_success(mock_repo):
    mock_repo.get_user_by_email.return_value = None
    mock_repo.create_user.return_value = "new_user_123"
    mock_repo.create_session.return_value = "session_123"

    resp = client.post("/api/auth/register", json={
        "full_name": "New User",
        "email": "NEW@EXAMPLE.COM",
        "password": "SecurePassword123!"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["email"] == "new@example.com"
    assert data["user"]["full_name"] == "New User"
    assert "password_hash" not in data["user"]
    assert "password" not in data["user"]
    assert mock_repo.create_user.called
    stored_doc = mock_repo.create_user.call_args[0][0]
    assert stored_doc["email"] == "new@example.com"
    assert stored_doc["password_hash"] != "SecurePassword123!"
    assert verify_password("SecurePassword123!", stored_doc["password_hash"])

@patch("app.auth.service.MongoRepository")
def test_login_unknown_email(mock_repo):
    mock_repo.get_user_by_email.return_value = None

    resp = client.post("/api/auth/login", json={
        "email": "notfound@example.com",
        "password": "SomePassword123"
    })
    assert resp.status_code == 401
    assert "invalid email or password" in resp.json()["detail"].lower()

@patch("app.auth.service.MongoRepository")
def test_login_wrong_password(mock_repo):
    stored_hash = hash_password("CorrectPassword123!")
    mock_repo.get_user_by_email.return_value = {
        "_id": "user_id_123",
        "email": "user@example.com",
        "full_name": "Test User",
        "password_hash": stored_hash,
        "is_active": True
    }

    resp = client.post("/api/auth/login", json={
        "email": "user@example.com",
        "password": "WrongPassword123"
    })
    assert resp.status_code == 401
    assert "invalid email or password" in resp.json()["detail"].lower()

@patch("app.auth.service.MongoRepository")
def test_login_success(mock_repo):
    stored_hash = hash_password("CorrectPassword123!")
    mock_repo.get_user_by_email.return_value = {
        "_id": "user_id_123",
        "email": "user@example.com",
        "full_name": "Test User",
        "password_hash": stored_hash,
        "is_active": True
    }
    mock_repo.create_session.return_value = "session_id_456"

    resp = client.post("/api/auth/login", json={
        "email": "USER@example.com",
        "password": "CorrectPassword123!"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["email"] == "user@example.com"
    assert data["user"]["full_name"] == "Test User"
    assert "password_hash" not in data["user"]
    assert "forecastiq_session" in resp.cookies
    assert data["session_token"] is not None

def test_me_unauthenticated():
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401

@patch("app.auth.service.MongoRepository")
def test_me_authenticated(mock_repo):
    mock_repo.get_session.return_value = {
        "session_token_hash": "some_hash",
        "user_id": "user_123",
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7)
    }
    mock_repo.get_user_by_id.return_value = {
        "_id": "user_123",
        "email": "active@example.com",
        "full_name": "Active User",
        "is_active": True,
        "password_hash": "secret_hash"
    }

    client.cookies.set("forecastiq_session", "valid_raw_token")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "active@example.com"
    assert data["full_name"] == "Active User"
    assert "password_hash" not in data
    client.cookies.clear()

@patch("app.auth.service.MongoRepository")
def test_logout_invalidates_session(mock_repo):
    mock_repo.delete_session.return_value = True

    client.cookies.set("forecastiq_session", "token_to_delete")
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert mock_repo.delete_session.called
    client.cookies.clear()
