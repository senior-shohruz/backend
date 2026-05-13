"""Public course/lesson endpoints — read-only for authenticated users."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.quiz import QuizQuestion
from app.schemas.course import CoursePublic, CourseWithLessons, LessonPublic, LessonSummary
from app.schemas.quiz import QuizQuestionForUser

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=list[CoursePublic])
async def list_courses(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[CoursePublic]:
    """List all published courses, ordered by order_index."""
    stmt = (
        select(Course, func.count(Lesson.id).label("lessons_count"))
        .outerjoin(Lesson, Lesson.course_id == Course.id)
        .where(Course.is_published.is_(True))
        .group_by(Course.id)
        .order_by(Course.order_index, Course.id)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        CoursePublic.model_validate({**course.__dict__, "lessons_count": count})
        for course, count in rows
    ]


@router.get("/{slug}", response_model=CourseWithLessons)
async def get_course_by_slug(
    slug: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CourseWithLessons:
    """Get a single course with its published lessons."""
    stmt = (
        select(Course)
        .where(Course.slug == slug, Course.is_published.is_(True))
        .options(selectinload(Course.lessons))
    )
    result = await db.execute(stmt)
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    published_lessons = [l for l in course.lessons if l.is_published]
    published_lessons.sort(key=lambda l: (l.order_index, l.id))

    return CourseWithLessons.model_validate({
        **course.__dict__,
        "lessons_count": len(published_lessons),
        "lessons": [LessonSummary.model_validate(l) for l in published_lessons],
    })


@router.get("/lessons/{lesson_id}", response_model=LessonPublic)
async def get_lesson(
    lesson_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LessonPublic:
    """Get a single lesson by ID."""
    stmt = (
        select(Lesson, func.count(QuizQuestion.id).label("questions_count"))
        .outerjoin(QuizQuestion, QuizQuestion.lesson_id == Lesson.id)
        .where(Lesson.id == lesson_id, Lesson.is_published.is_(True))
        .group_by(Lesson.id)
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    lesson, count = row
    return LessonPublic.model_validate({**lesson.__dict__, "questions_count": count})


@router.get("/lessons/{lesson_id}/quiz", response_model=list[QuizQuestionForUser])
async def get_lesson_quiz(
    lesson_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[QuizQuestion]:
    """Get the quiz questions for a lesson — without revealing correct answers."""
    # Verify lesson exists and is published
    lesson_check = await db.execute(
        select(Lesson.id).where(Lesson.id == lesson_id, Lesson.is_published.is_(True))
    )
    if lesson_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    result = await db.execute(
        select(QuizQuestion)
        .where(QuizQuestion.lesson_id == lesson_id)
        .order_by(QuizQuestion.order_index, QuizQuestion.id)
    )
    return list(result.scalars().all())
