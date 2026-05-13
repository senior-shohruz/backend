"""Progress endpoints — track lesson progress and code drafts."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.progress import (
    LessonProgress, ProgressStatus, QuizAttempt, UserBadge,
)
from app.schemas.progress import (
    LessonProgressUpdate, LessonProgressPublic,
    UserAnalytics, CourseProgressSummary, UserBadgePublic,
)
from app.services.gamification import xp_to_next_level, update_streak

router = APIRouter(prefix="/progress", tags=["progress"])


@router.put("/lessons/{lesson_id}", response_model=LessonProgressPublic)
async def update_lesson_progress(
    lesson_id: int,
    payload: LessonProgressUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LessonProgress:
    """Update progress for a lesson — autosave code, update completion %."""
    # Verify lesson
    lesson = (await db.execute(
        select(Lesson).where(Lesson.id == lesson_id, Lesson.is_published.is_(True))
    )).scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    # Get-or-create progress
    progress = (await db.execute(
        select(LessonProgress).where(
            LessonProgress.user_id == current_user.id,
            LessonProgress.lesson_id == lesson_id,
        )
    )).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if progress is None:
        progress = LessonProgress(
            user_id=current_user.id,
            lesson_id=lesson_id,
            status=ProgressStatus.IN_PROGRESS,
            started_at=now,
        )
        db.add(progress)

    if payload.status is not None:
        progress.status = payload.status
        if payload.status == ProgressStatus.COMPLETED and progress.completed_at is None:
            progress.completed_at = now
            progress.completion_percentage = 100.0
    if payload.completion_percentage is not None:
        progress.completion_percentage = payload.completion_percentage
    if payload.code_draft is not None:
        progress.code_draft = payload.code_draft.model_dump(exclude_none=True)

    if progress.started_at is None:
        progress.started_at = now

    await update_streak(db, current_user)
    await db.flush()
    return progress


@router.get("/lessons/{lesson_id}", response_model=LessonProgressPublic | None)
async def get_lesson_progress(
    lesson_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get current user's progress on a specific lesson."""
    progress = (await db.execute(
        select(LessonProgress).where(
            LessonProgress.user_id == current_user.id,
            LessonProgress.lesson_id == lesson_id,
        )
    )).scalar_one_or_none()
    return progress


@router.get("/me/analytics", response_model=UserAnalytics)
async def get_my_analytics(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserAnalytics:
    """Aggregate stats for the current user's dashboard."""
    completed = (await db.execute(
        select(func.count(LessonProgress.id)).where(
            LessonProgress.user_id == current_user.id,
            LessonProgress.status == ProgressStatus.COMPLETED,
        )
    )).scalar_one()

    in_progress = (await db.execute(
        select(func.count(LessonProgress.id)).where(
            LessonProgress.user_id == current_user.id,
            LessonProgress.status == ProgressStatus.IN_PROGRESS,
        )
    )).scalar_one()

    courses_started = (await db.execute(
        select(func.count(func.distinct(Lesson.course_id)))
        .join(LessonProgress, LessonProgress.lesson_id == Lesson.id)
        .where(LessonProgress.user_id == current_user.id)
    )).scalar_one()

    quizzes_taken = (await db.execute(
        select(func.count(QuizAttempt.id)).where(QuizAttempt.user_id == current_user.id)
    )).scalar_one()

    avg_score = (await db.execute(
        select(func.coalesce(func.avg(QuizAttempt.percentage), 0.0))
        .where(QuizAttempt.user_id == current_user.id)
    )).scalar_one()

    badges_count = (await db.execute(
        select(func.count(UserBadge.id)).where(UserBadge.user_id == current_user.id)
    )).scalar_one()

    return UserAnalytics(
        user_id=current_user.id,
        total_xp=current_user.xp,
        level=current_user.level,
        xp_to_next_level=xp_to_next_level(current_user.xp),
        streak_days=current_user.streak_days,
        lessons_completed=completed,
        lessons_in_progress=in_progress,
        courses_started=courses_started,
        quizzes_taken=quizzes_taken,
        avg_quiz_score=round(float(avg_score), 1),
        badges_earned=badges_count,
    )


@router.get("/me/courses", response_model=list[CourseProgressSummary])
async def get_my_course_progress(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CourseProgressSummary]:
    """List all started courses with per-course completion stats."""
    # All published courses with their lesson counts
    courses_stmt = (
        select(Course)
        .where(Course.is_published.is_(True))
        .options(selectinload(Course.lessons))
        .order_by(Course.order_index, Course.id)
    )
    courses = list((await db.execute(courses_stmt)).scalars().all())

    # Completed lesson IDs per course for this user
    completed_rows = (await db.execute(
        select(Lesson.course_id, func.count(LessonProgress.id))
        .join(LessonProgress, LessonProgress.lesson_id == Lesson.id)
        .where(
            LessonProgress.user_id == current_user.id,
            LessonProgress.status == ProgressStatus.COMPLETED,
        )
        .group_by(Lesson.course_id)
    )).all()
    completed_by_course = {row[0]: row[1] for row in completed_rows}

    out: list[CourseProgressSummary] = []
    for course in courses:
        published_lesson_count = sum(1 for l in course.lessons if l.is_published)
        completed = completed_by_course.get(course.id, 0)
        pct = (completed / published_lesson_count * 100.0) if published_lesson_count else 0.0
        out.append(CourseProgressSummary(
            course_id=course.id,
            course_title=course.title,
            course_slug=course.slug,
            icon_key=course.icon_key,
            total_lessons=published_lesson_count,
            completed_lessons=completed,
            progress_percentage=round(pct, 1),
        ))
    return out


@router.get("/me/badges", response_model=list[UserBadgePublic])
async def get_my_badges(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserBadge]:
    """List badges the current user has earned."""
    result = await db.execute(
        select(UserBadge)
        .where(UserBadge.user_id == current_user.id)
        .options(selectinload(UserBadge.badge))
        .order_by(UserBadge.earned_at.desc())
    )
    return list(result.scalars().all())
