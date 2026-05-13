"""Quiz submission endpoint — students submit answers and get scored."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.lesson import Lesson
from app.models.quiz import QuizQuestion
from app.models.progress import (
    QuizAttempt, LessonProgress, ProgressStatus,
)
from app.schemas.quiz import QuizSubmission, QuizResult, QuizAnswerResult
from app.services.gamification import (
    award_xp, update_streak, check_and_award_badges,
)

router = APIRouter(prefix="/quiz", tags=["quiz"])

PASS_THRESHOLD = 70.0  # percent


@router.post("/lessons/{lesson_id}/submit", response_model=QuizResult)
async def submit_quiz(
    lesson_id: int,
    submission: QuizSubmission,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuizResult:
    """Submit quiz answers, score them, award XP, and record the attempt."""
    # Load the lesson
    lesson = (await db.execute(
        select(Lesson).where(Lesson.id == lesson_id, Lesson.is_published.is_(True))
    )).scalar_one_or_none()
    if lesson is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    # Load all quiz questions
    questions = list((await db.execute(
        select(QuizQuestion).where(QuizQuestion.lesson_id == lesson_id)
    )).scalars().all())

    if not questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This lesson has no quiz questions",
        )

    questions_by_id = {q.id: q for q in questions}
    submitted_by_qid = {a.question_id: a.selected_key for a in submission.answers}

    # Score
    answer_results: list[QuizAnswerResult] = []
    correct_count = 0
    score = 0
    for q in questions:
        selected = submitted_by_qid.get(q.id, "")
        is_correct = selected == q.correct_option_key
        if is_correct:
            correct_count += 1
            score += q.points
        answer_results.append(QuizAnswerResult(
            question_id=q.id,
            selected_key=selected,
            correct_key=q.correct_option_key,
            is_correct=is_correct,
            explanation=q.explanation,
        ))

    total = len(questions)
    percentage = (correct_count / total * 100.0) if total > 0 else 0.0
    passed = percentage >= PASS_THRESHOLD

    # Persist attempt
    attempt = QuizAttempt(
        user_id=current_user.id,
        lesson_id=lesson_id,
        answers=[r.model_dump() for r in answer_results],
        score=score,
        total_questions=total,
        correct_count=correct_count,
        percentage=percentage,
    )
    db.add(attempt)
    await db.flush()

    # Award XP — only first time passing, scaled by accuracy
    xp_earned = 0
    if passed:
        # Check if user has already passed this lesson's quiz
        existing_pass = (await db.execute(
            select(QuizAttempt.id).where(
                QuizAttempt.user_id == current_user.id,
                QuizAttempt.lesson_id == lesson_id,
                QuizAttempt.percentage >= PASS_THRESHOLD,
                QuizAttempt.id != attempt.id,
            )
        )).scalar_one_or_none()

        if existing_pass is None:
            xp_earned = int(lesson.xp_reward * (percentage / 100.0))
            await award_xp(db, current_user, xp_earned)
            await update_streak(db, current_user)

            # Mark lesson as completed
            progress = (await db.execute(
                select(LessonProgress).where(
                    LessonProgress.user_id == current_user.id,
                    LessonProgress.lesson_id == lesson_id,
                )
            )).scalar_one_or_none()

            if progress is None:
                progress = LessonProgress(
                    user_id=current_user.id,
                    lesson_id=lesson_id,
                    started_at=datetime.now(timezone.utc),
                )
                db.add(progress)

            progress.status = ProgressStatus.COMPLETED
            progress.completion_percentage = 100.0
            progress.completed_at = datetime.now(timezone.utc)
            await db.flush()

            # Check for new badges
            await check_and_award_badges(db, current_user)

    return QuizResult(
        attempt_id=attempt.id,
        lesson_id=lesson_id,
        score=score,
        total_questions=total,
        correct_count=correct_count,
        percentage=percentage,
        xp_earned=xp_earned,
        passed=passed,
        answers=answer_results,
        submitted_at=attempt.submitted_at,
    )
