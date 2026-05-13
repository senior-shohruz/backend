"""SQLAlchemy models — import all here so Alembic and Base.metadata see them."""
from app.models.user import User, UserRole
from app.models.course import Course, CourseLevel
from app.models.lesson import Lesson
from app.models.quiz import QuizQuestion
from app.models.progress import (
    LessonProgress, ProgressStatus, QuizAttempt, Badge, UserBadge,
)

__all__ = [
    "User", "UserRole",
    "Course", "CourseLevel",
    "Lesson",
    "QuizQuestion",
    "LessonProgress", "ProgressStatus",
    "QuizAttempt",
    "Badge", "UserBadge",
]
