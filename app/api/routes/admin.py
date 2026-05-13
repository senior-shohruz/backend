"""Admin endpoints (CMS) — full CRUD for courses, lessons, quiz, users, plus analytics.

All routes require admin role (enforced via AdminUser dependency).
"""
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser
from app.core.security import hash_password
from app.db.session import get_db
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.quiz import QuizQuestion
from app.models.user import User, UserRole
from app.models.progress import (
    LessonProgress, ProgressStatus, QuizAttempt,
)
from app.schemas.course import (
    CourseCreate, CourseUpdate, CoursePublic,
    LessonCreate, LessonUpdate, LessonPublic,
)
from app.schemas.quiz import (
    QuizQuestionCreate, QuizQuestionUpdate, QuizQuestionAdmin,
)
from app.schemas.user import UserAdminView, UserAdminUpdate
from app.schemas.progress import AdminDashboardStats, PopularCourse

router = APIRouter(prefix="/admin", tags=["admin"])


# ═════════════════════════════════════════════════════════════════════
# COURSE MANAGEMENT
# ═════════════════════════════════════════════════════════════════════

@router.get("/courses", response_model=list[CoursePublic])
async def admin_list_courses(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Optional[str] = Query(None, max_length=200),
    is_published: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[CoursePublic]:
    """List ALL courses (including unpublished) for admin."""
    stmt = (
        select(Course, func.count(Lesson.id).label("lessons_count"))
        .outerjoin(Lesson, Lesson.course_id == Course.id)
        .group_by(Course.id)
    )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Course.title.ilike(like), Course.description.ilike(like)))
    if is_published is not None:
        stmt = stmt.where(Course.is_published.is_(is_published))

    stmt = stmt.order_by(Course.order_index, Course.id).offset(skip).limit(limit)
    rows = (await db.execute(stmt)).all()
    return [
        CoursePublic.model_validate({**course.__dict__, "lessons_count": count})
        for course, count in rows
    ]


@router.post("/courses", response_model=CoursePublic, status_code=status.HTTP_201_CREATED)
async def admin_create_course(
    payload: CourseCreate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CoursePublic:
    """Create a new course."""
    existing = await db.execute(select(Course).where(Course.slug == payload.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already in use")

    course = Course(**payload.model_dump())
    db.add(course)
    await db.flush()
    await db.refresh(course)
    return CoursePublic.model_validate({**course.__dict__, "lessons_count": 0})


@router.patch("/courses/{course_id}", response_model=CoursePublic)
async def admin_update_course(
    course_id: int,
    payload: CourseUpdate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CoursePublic:
    """Update a course (partial)."""
    course = (await db.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, field, value)

    await db.flush()
    lessons_count = (await db.execute(
        select(func.count(Lesson.id)).where(Lesson.course_id == course_id)
    )).scalar_one()
    return CoursePublic.model_validate({**course.__dict__, "lessons_count": lessons_count})


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_course(
    course_id: int,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a course (and cascade its lessons + quiz)."""
    course = (await db.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    await db.delete(course)
    await db.flush()


# ═════════════════════════════════════════════════════════════════════
# LESSON MANAGEMENT
# ═════════════════════════════════════════════════════════════════════

@router.get("/lessons", response_model=list[LessonPublic])
async def admin_list_lessons(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    course_id: Optional[int] = None,
    search: Optional[str] = Query(None, max_length=200),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[LessonPublic]:
    """List lessons, optionally filtered by course."""
    stmt = (
        select(Lesson, func.count(QuizQuestion.id).label("questions_count"))
        .outerjoin(QuizQuestion, QuizQuestion.lesson_id == Lesson.id)
        .group_by(Lesson.id)
    )
    if course_id is not None:
        stmt = stmt.where(Lesson.course_id == course_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(Lesson.title.ilike(like))

    stmt = stmt.order_by(Lesson.course_id, Lesson.order_index, Lesson.id).offset(skip).limit(limit)
    rows = (await db.execute(stmt)).all()
    return [
        LessonPublic.model_validate({**lesson.__dict__, "questions_count": count})
        for lesson, count in rows
    ]


@router.post("/lessons", response_model=LessonPublic, status_code=status.HTTP_201_CREATED)
async def admin_create_lesson(
    payload: LessonCreate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LessonPublic:
    """Create a new lesson."""
    course = (await db.execute(
        select(Course).where(Course.id == payload.course_id)
    )).scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    lesson = Lesson(**payload.model_dump())
    db.add(lesson)
    await db.flush()
    await db.refresh(lesson)
    return LessonPublic.model_validate({**lesson.__dict__, "questions_count": 0})


@router.patch("/lessons/{lesson_id}", response_model=LessonPublic)
async def admin_update_lesson(
    lesson_id: int,
    payload: LessonUpdate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LessonPublic:
    """Update a lesson (partial)."""
    lesson = (await db.execute(
        select(Lesson).where(Lesson.id == lesson_id)
    )).scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    data = payload.model_dump(exclude_unset=True)
    if "course_id" in data:
        course = (await db.execute(
            select(Course).where(Course.id == data["course_id"])
        )).scalar_one_or_none()
        if course is None:
            raise HTTPException(status_code=400, detail="Target course not found")

    for field, value in data.items():
        setattr(lesson, field, value)

    await db.flush()
    qcount = (await db.execute(
        select(func.count(QuizQuestion.id)).where(QuizQuestion.lesson_id == lesson_id)
    )).scalar_one()
    return LessonPublic.model_validate({**lesson.__dict__, "questions_count": qcount})


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_lesson(
    lesson_id: int,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a lesson."""
    lesson = (await db.execute(
        select(Lesson).where(Lesson.id == lesson_id)
    )).scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    await db.delete(lesson)
    await db.flush()


# ═════════════════════════════════════════════════════════════════════
# QUIZ MANAGEMENT
# ═════════════════════════════════════════════════════════════════════

@router.get("/lessons/{lesson_id}/questions", response_model=list[QuizQuestionAdmin])
async def admin_list_questions(
    lesson_id: int,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[QuizQuestion]:
    """List all quiz questions for a lesson — INCLUDING correct answers."""
    result = await db.execute(
        select(QuizQuestion)
        .where(QuizQuestion.lesson_id == lesson_id)
        .order_by(QuizQuestion.order_index, QuizQuestion.id)
    )
    return list(result.scalars().all())


@router.post(
    "/questions",
    response_model=QuizQuestionAdmin,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_question(
    payload: QuizQuestionCreate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuizQuestion:
    """Create a quiz question."""
    lesson = (await db.execute(
        select(Lesson).where(Lesson.id == payload.lesson_id)
    )).scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    data = payload.model_dump()
    data["options"] = [opt for opt in data["options"]]  # already dicts via model_dump
    question = QuizQuestion(**data)
    db.add(question)
    await db.flush()
    await db.refresh(question)
    return question


@router.patch("/questions/{question_id}", response_model=QuizQuestionAdmin)
async def admin_update_question(
    question_id: int,
    payload: QuizQuestionUpdate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuizQuestion:
    """Update a quiz question (partial). Validates that correct_option_key matches options."""
    question = (await db.execute(
        select(QuizQuestion).where(QuizQuestion.id == question_id)
    )).scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    data = payload.model_dump(exclude_unset=True)

    # Determine final state for validation
    final_options = data.get("options")
    if final_options is not None:
        data["options"] = [opt if isinstance(opt, dict) else opt.model_dump() for opt in final_options]
        final_keys = {o["key"] for o in data["options"]}
    else:
        final_keys = {o["key"] for o in question.options}

    final_correct = data.get("correct_option_key", question.correct_option_key)
    if final_correct not in final_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"correct_option_key '{final_correct}' must match one of the option keys",
        )

    for field, value in data.items():
        setattr(question, field, value)

    await db.flush()
    return question


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_question(
    question_id: int,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a quiz question."""
    question = (await db.execute(
        select(QuizQuestion).where(QuizQuestion.id == question_id)
    )).scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    await db.delete(question)
    await db.flush()


# ═════════════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ═════════════════════════════════════════════════════════════════════

@router.get("/users", response_model=list[UserAdminView])
async def admin_list_users(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Optional[str] = Query(None, max_length=100),
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[User]:
    """List all users with filtering."""
    stmt = select(User)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(
            User.email.ilike(like),
            User.username.ilike(like),
            User.full_name.ilike(like),
        ))
    if role is not None:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))

    stmt = stmt.order_by(desc(User.created_at)).offset(skip).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


@router.get("/users/{user_id}", response_model=UserAdminView)
async def admin_get_user(
    user_id: int,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get a single user."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserAdminView)
async def admin_update_user(
    user_id: int,
    payload: UserAdminUpdate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Update a user — change role, activate/deactivate, etc."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent admin from demoting themselves
    if user.id == admin.id and payload.role is not None and payload.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot demote your own admin account",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await db.flush()
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_user(
    user_id: int,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a user (cascades progress, attempts, badges)."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db.delete(user)
    await db.flush()


# ═════════════════════════════════════════════════════════════════════
# ANALYTICS DASHBOARD
# ═════════════════════════════════════════════════════════════════════

@router.get("/dashboard", response_model=AdminDashboardStats)
async def admin_dashboard(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminDashboardStats:
    """Aggregate metrics for the admin dashboard."""
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_users_7d = (await db.execute(
        select(func.count(User.id)).where(User.last_active_at >= seven_days_ago)
    )).scalar_one()
    new_users_30d = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= thirty_days_ago)
    )).scalar_one()

    total_courses = (await db.execute(select(func.count(Course.id)))).scalar_one()
    published_courses = (await db.execute(
        select(func.count(Course.id)).where(Course.is_published.is_(True))
    )).scalar_one()
    total_lessons = (await db.execute(select(func.count(Lesson.id)))).scalar_one()
    total_attempts = (await db.execute(select(func.count(QuizAttempt.id)))).scalar_one()
    completed_total = (await db.execute(
        select(func.count(LessonProgress.id)).where(
            LessonProgress.status == ProgressStatus.COMPLETED
        )
    )).scalar_one()

    # Popular courses (by distinct enrolled users)
    popular_rows = (await db.execute(
        select(
            Course.id,
            Course.title,
            func.count(func.distinct(LessonProgress.user_id)).label("enrolled"),
        )
        .join(Lesson, Lesson.course_id == Course.id)
        .outerjoin(LessonProgress, LessonProgress.lesson_id == Lesson.id)
        .group_by(Course.id, Course.title)
        .order_by(desc("enrolled"))
        .limit(5)
    )).all()

    popular = []
    for course_id, title, enrolled in popular_rows:
        # Completion rate per course
        total_lessons_in = (await db.execute(
            select(func.count(Lesson.id)).where(Lesson.course_id == course_id)
        )).scalar_one()

        completed_lp = (await db.execute(
            select(func.count(LessonProgress.id))
            .join(Lesson, Lesson.id == LessonProgress.lesson_id)
            .where(
                Lesson.course_id == course_id,
                LessonProgress.status == ProgressStatus.COMPLETED,
            )
        )).scalar_one()

        denom = (enrolled or 0) * (total_lessons_in or 0)
        rate = (completed_lp / denom * 100.0) if denom else 0.0
        popular.append(PopularCourse(
            course_id=course_id,
            title=title,
            enrolled_users=enrolled or 0,
            completion_rate=round(rate, 1),
        ))

    return AdminDashboardStats(
        total_users=total_users,
        active_users_last_7d=active_users_7d,
        new_users_last_30d=new_users_30d,
        total_courses=total_courses,
        published_courses=published_courses,
        total_lessons=total_lessons,
        total_quiz_attempts=total_attempts,
        lessons_completed_total=completed_total,
        popular_courses=popular,
    )
