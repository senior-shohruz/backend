"""Pydantic schemas for quiz questions and submissions."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class QuizOption(BaseModel):
    key: str = Field(min_length=1, max_length=10)
    text: str = Field(min_length=1)


class QuizQuestionBase(BaseModel):
    question_text: str = Field(min_length=1)
    options: list[QuizOption] = Field(min_length=2, max_length=6)
    correct_option_key: str = Field(min_length=1, max_length=10)
    explanation: Optional[str] = None
    points: int = Field(default=1, ge=1)
    order_index: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_correct_key_in_options(self):
        keys = {opt.key for opt in self.options}
        if self.correct_option_key not in keys:
            raise ValueError(
                f"correct_option_key '{self.correct_option_key}' must match one of the option keys: {keys}"
            )
        if len(keys) != len(self.options):
            raise ValueError("Option keys must be unique")
        return self


class QuizQuestionCreate(QuizQuestionBase):
    lesson_id: int


class QuizQuestionUpdate(BaseModel):
    question_text: Optional[str] = Field(default=None, min_length=1)
    options: Optional[list[QuizOption]] = Field(default=None, min_length=2, max_length=6)
    correct_option_key: Optional[str] = None
    explanation: Optional[str] = None
    points: Optional[int] = Field(default=None, ge=1)
    order_index: Optional[int] = Field(default=None, ge=0)


class QuizQuestionAdmin(QuizQuestionBase):
    """Admin view — includes the correct answer."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    lesson_id: int
    created_at: datetime


class QuizQuestionForUser(BaseModel):
    """User-facing view — hides the correct answer."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_text: str
    options: list[QuizOption]
    points: int
    order_index: int


# ───────────── Submission ─────────────

class QuizAnswer(BaseModel):
    question_id: int
    selected_key: str


class QuizSubmission(BaseModel):
    answers: list[QuizAnswer] = Field(min_length=1)


class QuizAnswerResult(BaseModel):
    question_id: int
    selected_key: str
    correct_key: str
    is_correct: bool
    explanation: Optional[str] = None


class QuizResult(BaseModel):
    attempt_id: int
    lesson_id: int
    score: int
    total_questions: int
    correct_count: int
    percentage: float
    xp_earned: int
    passed: bool
    answers: list[QuizAnswerResult]
    submitted_at: datetime
