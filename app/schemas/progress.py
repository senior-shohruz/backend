"""Schemas for progress tracking, analytics, and AI teacher."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.progress import ProgressStatus


# ───────────── Progress ─────────────

class CodeDraft(BaseModel):
    html: Optional[str] = None
    css: Optional[str] = None
    js: Optional[str] = None


class LessonProgressUpdate(BaseModel):
    status: Optional[ProgressStatus] = None
    completion_percentage: Optional[float] = Field(default=None, ge=0, le=100)
    code_draft: Optional[CodeDraft] = None


class LessonProgressPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lesson_id: int
    status: ProgressStatus
    completion_percentage: float
    code_draft: Optional[dict] = None
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    updated_at: datetime


# ───────────── Analytics ─────────────

class UserAnalytics(BaseModel):
    """Summary stats for a user's dashboard."""
    user_id: int
    total_xp: int
    level: int
    xp_to_next_level: int
    streak_days: int
    lessons_completed: int
    lessons_in_progress: int
    courses_started: int
    quizzes_taken: int
    avg_quiz_score: float
    badges_earned: int


class CourseProgressSummary(BaseModel):
    course_id: int
    course_title: str
    course_slug: str
    icon_key: Optional[str]
    total_lessons: int
    completed_lessons: int
    progress_percentage: float


class AdminDashboardStats(BaseModel):
    """Admin overview metrics."""
    total_users: int
    active_users_last_7d: int
    new_users_last_30d: int
    total_courses: int
    published_courses: int
    total_lessons: int
    total_quiz_attempts: int
    lessons_completed_total: int
    popular_courses: list["PopularCourse"]


class PopularCourse(BaseModel):
    course_id: int
    title: str
    enrolled_users: int
    completion_rate: float


AdminDashboardStats.model_rebuild()


# ───────────── Badges ─────────────

class BadgePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    description: str
    icon_url: Optional[str]


class UserBadgePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    badge: BadgePublic
    earned_at: datetime


# ───────────── AI Teacher ─────────────

class AIAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    lesson_id: Optional[int] = None
    code_context: Optional[CodeDraft] = None


class AIAskResponse(BaseModel):
    answer: str
    lesson_id: Optional[int] = None
