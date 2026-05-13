"""Gamification logic: XP, levels, badge awarding."""
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.user import User
from app.models.progress import (
    LessonProgress, ProgressStatus, QuizAttempt, Badge, UserBadge,
)


# ───────────── XP / Levels ─────────────

def xp_required_for_level(level: int) -> int:
    """Total XP needed to reach a given level. Quadratic curve."""
    if level <= 1:
        return 0
    return 50 * (level - 1) * level  # L2=100, L3=300, L4=600, L5=1000, L10=4500


def level_for_xp(xp: int) -> int:
    """Highest level a user has earned given their total XP."""
    level = 1
    while xp_required_for_level(level + 1) <= xp:
        level += 1
        if level > 100:  # safety cap
            break
    return level


def xp_to_next_level(xp: int) -> int:
    """How much XP until the next level."""
    current = level_for_xp(xp)
    return xp_required_for_level(current + 1) - xp


async def award_xp(db: AsyncSession, user: User, amount: int) -> tuple[int, bool]:
    """Add XP to user, recalculate level. Returns (new_level, leveled_up)."""
    if amount <= 0:
        return user.level, False

    old_level = user.level
    user.xp += amount
    user.level = level_for_xp(user.xp)
    user.last_active_at = datetime.now(timezone.utc)
    leveled_up = user.level > old_level

    await db.flush()
    return user.level, leveled_up


# ───────────── Streaks ─────────────

async def update_streak(db: AsyncSession, user: User) -> int:
    """Update the user's daily streak based on last_active_at. Returns new streak."""
    now = datetime.now(timezone.utc)
    last = user.last_active_at

    if last is None:
        user.streak_days = 1
    else:
        # Normalize to dates for day comparison
        last_date = last.date()
        today = now.date()
        delta = (today - last_date).days

        if delta == 0:
            pass  # already counted today
        elif delta == 1:
            user.streak_days += 1
        else:
            user.streak_days = 1  # broken streak

    user.last_active_at = now
    await db.flush()
    return user.streak_days


# ───────────── Badge awarding ─────────────

async def check_and_award_badges(db: AsyncSession, user: User) -> list[Badge]:
    """Check all badges and award any newly-earned ones to the user."""
    # Compute user stats
    completed_count = (
        await db.execute(
            select(func.count(LessonProgress.id)).where(
                LessonProgress.user_id == user.id,
                LessonProgress.status == ProgressStatus.COMPLETED,
            )
        )
    ).scalar_one()

    quiz_count = (
        await db.execute(
            select(func.count(QuizAttempt.id)).where(QuizAttempt.user_id == user.id)
        )
    ).scalar_one()

    perfect_quiz_count = (
        await db.execute(
            select(func.count(QuizAttempt.id)).where(
                QuizAttempt.user_id == user.id,
                QuizAttempt.percentage >= 100.0,
            )
        )
    ).scalar_one()

    stats = {
        "lessons_completed": completed_count,
        "quizzes_taken": quiz_count,
        "perfect_quizzes": perfect_quiz_count,
        "level": user.level,
        "streak_days": user.streak_days,
        "xp": user.xp,
    }

    # Already-earned badge IDs
    earned_ids = set(
        (
            await db.execute(
                select(UserBadge.badge_id).where(UserBadge.user_id == user.id)
            )
        ).scalars().all()
    )

    # All badges
    all_badges = (await db.execute(select(Badge))).scalars().all()

    newly_earned = []
    for badge in all_badges:
        if badge.id in earned_ids:
            continue
        if _meets_criteria(badge.criteria, stats):
            db.add(UserBadge(user_id=user.id, badge_id=badge.id))
            newly_earned.append(badge)

    if newly_earned:
        await db.flush()
    return newly_earned


def _meets_criteria(criteria: dict, stats: dict) -> bool:
    """Check whether stats satisfy the badge criteria."""
    if not criteria:
        return False
    crit_type = criteria.get("type")
    threshold = criteria.get("count", 0)
    return stats.get(crit_type, 0) >= threshold
