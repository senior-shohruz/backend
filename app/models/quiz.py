"""Quiz models — questions and multiple-choice options stored as JSON."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.lesson import Lesson


class QuizQuestion(Base):
    """A single multiple-choice question belonging to a lesson.

    Options stored as JSON: [{"key": "a", "text": "..."}, ...]
    correct_option_key references one of the option keys.
    """
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Stored as: [{"key": "a", "text": "Answer A"}, {"key": "b", "text": "Answer B"}, ...]
    options: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    correct_option_key: Mapped[str] = mapped_column(String(10), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    points: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    lesson: Mapped["Lesson"] = relationship(back_populates="quiz_questions")

    def __repr__(self) -> str:
        return f"<QuizQuestion id={self.id} lesson_id={self.lesson_id}>"
