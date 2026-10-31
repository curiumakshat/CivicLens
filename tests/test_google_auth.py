"""Comprehensive automated test suite for Google OAuth2 and CivicLens Authentication."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import Report, User


client = TestClient(app)


def test_01_civiclens_starts_and_health_check():
    """1. CivicLens starts without errors and health check responds."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "CivicLens" in data["service"]


def test_02_login_page_serves_react_entrypoint():
    """2. Login page serves the React frontend entrypoint."""
    response = client.get("/login")
    assert response.status_code == 200
    html = response.text
    assert '<div id="root"></div>' in html
    assert "/assets/" in html


def test_03_google_login_redirects_to_google_oauth():
    """3. Clicking Continue with Google initiates OAuth and redirects to Google."""
    response = client.get("/auth/google/login", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    location = response.headers.get("location")
    assert location is not None
    assert "accounts.google.com" in location
    assert "client_id=" in location
    assert "redirect_uri=" in location
    assert "response_type=code" in location
    assert "scope=" in location
    assert "state=" in location


@patch("app.routes.auth.oauth.google.authorize_access_token")
def test_04_successful_google_login_creates_and_retrieves_user(mock_token):
    """4. Successful Google login creates new user and subsequent login retrieves it."""
    fake_sub = "google_user_sub_998877"
    fake_email = "citizen.rajesh@gmail.com"
    fake_name = "Rajesh Resident"
    fake_picture = "https://lh3.googleusercontent.com/a/avatar99.jpg"

    mock_token.return_value = {
        "access_token": "fake_access_token",
        "id_token": "fake_id_token",
        "userinfo": {
            "sub": fake_sub,
            "email": fake_email,
            "email_verified": True,
            "name": fake_name,
            "picture": fake_picture,
        },
    }

    # 4a. First login creates user
    test_client = TestClient(app)
    res = test_client.get("/auth/google/callback", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/tracker"
    assert "civiclens_verified" in res.headers.get("set-cookie", "")

    # Check database
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.google_sub == fake_sub))
        assert user is not None
        assert user.email == fake_email
        assert user.display_name == fake_name
        assert user.avatar_url == fake_picture
        assert user.is_verified is True
        assert user.auth_provider == "google"
        user_id = user.id

    # 4b. Subsequent login retrieves the same user without duplicate creation
    res2 = test_client.get("/auth/google/callback", follow_redirects=False)
    assert res2.status_code == 303

    with SessionLocal() as db:
        matching_users = db.scalars(select(User).where(User.google_sub == fake_sub)).all()
        assert len(matching_users) == 1
        assert matching_users[0].id == user_id


@patch("app.routes.auth.oauth.google.authorize_access_token")
def test_05_authenticated_user_can_submit_civic_report(mock_token):
    """5 & 6. Authenticated user can submit civic report, linked to their resident ID."""
    fake_sub = "google_user_sub_report_test_1"
    fake_email = "reporter.priya@gmail.com"
    fake_name = "Priya Sharma"

    mock_token.return_value = {
        "access_token": "fake_access_token",
        "id_token": "fake_id_token",
        "userinfo": {
            "sub": fake_sub,
            "email": fake_email,
            "email_verified": True,
            "name": fake_name,
            "picture": None,
        },
    }

    test_client = TestClient(app)
    # Login via Google
    res_login = test_client.get("/auth/google/callback", follow_redirects=False)
    assert res_login.status_code == 303

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.google_sub == fake_sub))
        assert user is not None
        user_id = user.id

    # Submit report
    report_payload = {
        "category": "Roads & potholes",
        "title": "Severe pothole near SMS Hospital Crossing",
        "description": "Deep crater damaging tyres during evening traffic.",
        "latitude": 26.9124,
        "longitude": 75.7873,
    }
    res_report = test_client.post("/api/reports", json=report_payload)
    assert res_report.status_code == 201
    report_data = res_report.json()
    assert report_data["status"] == "success"
    assert report_data["reporter_id"] == user_id
    report_id = report_data["report_id"]

    # Verify report in database is associated with correct resident
    with SessionLocal() as db:
        db_report = db.scalar(select(Report).where(Report.id == report_id))
        assert db_report is not None
        assert db_report.reporter_id == user_id
        assert "Severe pothole" in db_report.description
        assert db_report.category == "Roads & potholes"


def test_06_logout_clears_application_session():
    """7. Logout clears session and redirects to login page."""
    test_client = TestClient(app)
    # Establish a session via OTP
    req_res = test_client.post("/auth/request-otp", json={"contact": "9876543210"})
    demo_code = req_res.json()["demo_code"]
    test_client.post("/auth/verify-otp", json={"contact": "9876543210", "otp": demo_code})

    # Verify logged in
    me_res = test_client.get("/auth/me")
    assert me_res.json()["authenticated"] is True

    # Logout
    logout_res = test_client.get("/auth/logout", follow_redirects=False)
    assert logout_res.status_code == 303
    assert logout_res.headers["location"] == "/login"

    # Verify logged out
    me_res2 = test_client.get("/auth/me")
    assert me_res2.json()["authenticated"] is False


@patch("app.routes.auth.oauth.google.authorize_access_token")
def test_07_unverified_email_is_rejected(mock_token):
    """8. Unverified Google email address is rejected for security."""
    mock_token.return_value = {
        "access_token": "fake_access_token",
        "id_token": "fake_id_token",
        "userinfo": {
            "sub": "unverified_sub_123",
            "email": "unverified@gmail.com",
            "email_verified": False,
            "name": "Unverified User",
        },
    }

    test_client = TestClient(app)
    res = test_client.get("/auth/google/callback", follow_redirects=False)
    assert res.status_code in (303, 307)
    location = res.headers["location"]
    assert "error=" in location
    assert "not" in location.lower() and "verified" in location.lower()


def test_08_failed_authentication_error_query_param():
    """9. Google cancellation or error query param returns the React app."""
    res = client.get("/auth/google/callback?error=access_denied", follow_redirects=True)
    assert res.status_code == 200
    assert '<div id="root"></div>' in res.text


def test_09_existing_otp_functionality_intact():
    """10. Existing OTP login flow remains fully functional."""
    # Request OTP
    res_req = client.post("/auth/request-otp", json={"contact": "9123456789"})
    assert res_req.status_code == 200
    demo_code = res_req.json().get("demo_code")
    assert demo_code is not None

    # Verify OTP
    test_client = TestClient(app)
    res_verify = test_client.post("/auth/verify-otp", json={"contact": "9123456789", "otp": demo_code})
    assert res_verify.status_code == 200
    assert res_verify.json()["verified"] is True
    assert res_verify.json()["redirect_url"] == "/tracker"
