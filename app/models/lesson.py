"""Lesson model — belongs to a course, contains video + content."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.quiz import QuizQuestion
    from app.models.progress import LessonProgress


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Markdown / rich text explanation
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Video — either external URL (YouTube etc.) or uploaded file path
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Optional code starter for the editor
    starter_code_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    starter_code_css: Mapped[str | None] = mapped_column(Text, nullable=True)
    starter_code_js: Mapped[str | None] = mapped_column(Text, nullable=True)

    # XP awarded on completion
    xp_reward: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="lessons")
    quiz_questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="QuizQuestion.order_index",
    )
    progress_entries: Mapped[list["LessonProgress"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Lesson id={self.id} title={self.title!r}>"
