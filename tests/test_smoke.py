"""Smoke test — verifies that all modules import cleanly and gamification logic works.

This avoids needing a live PostgreSQL connection. Run with: python -m pytest tests/
"""
import os
# Set required env BEFORE importing app
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("SYNC_DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")


def test_imports_clean():
    """All package imports should succeed."""
    from app.main import app
    from app.models import User, Course, Lesson, QuizQuestion
    from app.schemas.user import UserRegister, Token
    from app.schemas.course import CourseCreate, LessonCreate
    from app.schemas.quiz import QuizQuestionCreate, QuizSubmission
    assert app is not None
    assert User is not None


def test_password_hashing():
    from app.core.security import hash_password, verify_password
    h = hash_password("hello123!")
    assert h != "hello123!"
    assert verify_password("hello123!", h) is True
    assert verify_password("wrong", h) is False


def test_password_hashing_long_input():
    """Bcrypt has a 72-byte limit; passwords longer than that should still hash & verify."""
    from app.core.security import hash_password, verify_password
    long_pw = "x" * 200
    h = hash_password(long_pw)
    assert verify_password(long_pw, h) is True
    # First 72 bytes match → bcrypt treats them the same. Anything shorter
    # that doesn't share the same 72-byte prefix should fail.
    assert verify_password("y" * 200, h) is False


def test_jwt_roundtrip():
    from app.core.security import create_access_token, decode_token
    token = create_access_token(subject=42, role="user")
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["role"] == "user"
    assert payload["type"] == "access"


def test_decode_invalid_token():
    from app.core.security import decode_token
    assert decode_token("not.a.valid.jwt") is None
    assert decode_token("") is None


def test_xp_level_curve():
    from app.services.gamification import (
        xp_required_for_level, level_for_xp, xp_to_next_level,
    )
    assert xp_required_for_level(1) == 0
    assert xp_required_for_level(2) == 100
    assert xp_required_for_level(3) == 300
    assert xp_required_for_level(5) == 1000

    assert level_for_xp(0) == 1
    assert level_for_xp(99) == 1
    assert level_for_xp(100) == 2
    assert level_for_xp(299) == 2
    assert level_for_xp(300) == 3

    assert xp_to_next_level(0) == 100
    assert xp_to_next_level(50) == 50
    assert xp_to_next_level(100) == 200  # at L2, need 300 total → 200 more


def test_quiz_question_validation():
    from app.schemas.quiz import QuizQuestionCreate, QuizOption
    import pytest

    # Valid
    q = QuizQuestionCreate(
        lesson_id=1,
        question_text="What is HTML?",
        options=[
            QuizOption(key="a", text="Markup language"),
            QuizOption(key="b", text="Programming language"),
        ],
        correct_option_key="a",
        explanation="HTML is a markup language",
    )
    assert q.correct_option_key == "a"

    # Invalid - correct key not in options
    with pytest.raises(Exception):
        QuizQuestionCreate(
            lesson_id=1,
            question_text="Q?",
            options=[QuizOption(key="a", text="A"), QuizOption(key="b", text="B")],
            correct_option_key="z",
        )

    # Invalid - duplicate keys
    with pytest.raises(Exception):
        QuizQuestionCreate(
            lesson_id=1,
            question_text="Q?",
            options=[QuizOption(key="a", text="A"), QuizOption(key="a", text="B")],
            correct_option_key="a",
        )


def test_user_register_validation():
    from app.schemas.user import UserRegister
    import pytest

    # Valid
    u = UserRegister(email="user@example.com", username="alex_99", password="strongpw123")
    assert u.username == "alex_99"

    # Invalid - bad username chars
    with pytest.raises(Exception):
        UserRegister(email="user@example.com", username="alex 99", password="strongpw123")

    # Invalid - short password
    with pytest.raises(Exception):
        UserRegister(email="user@example.com", username="alex", password="short")


def test_app_routes_registered():
    from app.main import app
    paths = {route.path for route in app.routes}
    # Spot-check key endpoints
    assert any("/auth/login" in p for p in paths)
    assert any("/auth/register" in p for p in paths)
    assert any("/courses" in p for p in paths)
    assert any("/admin/courses" in p for p in paths)
    assert any("/admin/users" in p for p in paths)
    assert any("/admin/dashboard" in p for p in paths)
    assert any("/quiz/lessons" in p for p in paths)
    assert any("/ai/ask" in p for p in paths)
    assert "/" in paths
    assert "/health" in paths
