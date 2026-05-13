"""Pydantic schemas for courses and lessons."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.course import CourseLevel


# ───────────── Course ─────────────

class CourseBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    short_description: Optional[str] = Field(default=None, max_length=300)
    thumbnail_url: Optional[str] = Field(default=None, max_length=500)
    level: CourseLevel = CourseLevel.BEGINNER
    icon_key: Optional[str] = Field(default=None, max_length=50)
    estimated_minutes: int = Field(default=0, ge=0)
    order_index: int = Field(default=0, ge=0)
    is_published: bool = False


class CourseCreate(CourseBase):
    slug: str = Field(min_length=1, max_length=220, pattern=r"^[a-z0-9-]+$")


class CourseUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, min_length=1)
    short_description: Optional[str] = Field(default=None, max_length=300)
    thumbnail_url: Optional[str] = Field(default=None, max_length=500)
    level: Optional[CourseLevel] = None
    icon_key: Optional[str] = Field(default=None, max_length=50)
    estimated_minutes: Optional[int] = Field(default=None, ge=0)
    order_index: Optional[int] = Field(default=None, ge=0)
    is_published: Optional[bool] = None


class CoursePublic(CourseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    created_at: datetime
    updated_at: datetime
    lessons_count: int = 0


class CourseWithLessons(CoursePublic):
    """Course detail view including its lessons (summary)."""
    lessons: list["LessonSummary"] = []


# ───────────── Lesson ─────────────

class LessonBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)
    content: str = ""
    video_url: Optional[str] = Field(default=None, max_length=500)
    video_duration_seconds: int = Field(default=0, ge=0)
    starter_code_html: Optional[str] = None
    starter_code_css: Optional[str] = None
    starter_code_js: Optional[str] = None
    xp_reward: int = Field(default=10, ge=0)
    order_index: int = Field(default=0, ge=0)
    is_published: bool = False


class LessonCreate(LessonBase):
    course_id: int
    slug: str = Field(min_length=1, max_length=220, pattern=r"^[a-z0-9-]+$")


class LessonUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)
    content: Optional[str] = None
    video_url: Optional[str] = Field(default=None, max_length=500)
    video_duration_seconds: Optional[int] = Field(default=None, ge=0)
    starter_code_html: Optional[str] = None
    starter_code_css: Optional[str] = None
    starter_code_js: Optional[str] = None
    xp_reward: Optional[int] = Field(default=None, ge=0)
    order_index: Optional[int] = Field(default=None, ge=0)
    is_published: Optional[bool] = None
    course_id: Optional[int] = None


class LessonSummary(BaseModel):
    """Light view used inside course lists."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    description: Optional[str]
    video_duration_seconds: int
    xp_reward: int
    order_index: int
    is_published: bool


class LessonPublic(LessonBase):
    """Full lesson view."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    course_id: int
    created_at: datetime
    updated_at: datetime
    questions_count: int = 0


# Forward-ref resolution for CourseWithLessons → LessonSummary
CourseWithLessons.model_rebuild()
