"""Initial data seeding: first admin user and default badges."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.progress import Badge


DEFAULT_BADGES = [
    {
        "key": "first_lesson",
        "name": "First Steps",
        "description": "Complete your first lesson",
        "criteria": {"type": "lessons_completed", "count": 1},
    },
    {
        "key": "ten_lessons",
        "name": "Dedicated Learner",
        "description": "Complete 10 lessons",
        "criteria": {"type": "lessons_completed", "count": 10},
    },
    {
        "key": "fifty_lessons",
        "name": "Frontend Apprentice",
        "description": "Complete 50 lessons",
        "criteria": {"type": "lessons_completed", "count": 50},
    },
    {
        "key": "first_quiz",
        "name": "Quiz Rookie",
        "description": "Take your first quiz",
        "criteria": {"type": "quizzes_taken", "count": 1},
    },
    {
        "key": "perfect_quiz",
        "name": "Perfectionist",
        "description": "Score 100% on a quiz",
        "criteria": {"type": "perfect_quizzes", "count": 1},
    },
    {
        "key": "ten_perfect_quizzes",
        "name": "Quiz Master",
        "description": "Score 100% on 10 different quizzes",
        "criteria": {"type": "perfect_quizzes", "count": 10},
    },
    {
        "key": "level_5",
        "name": "Rising Star",
        "description": "Reach level 5",
        "criteria": {"type": "level", "count": 5},
    },
    {
        "key": "level_10",
        "name": "Frontend Pro",
        "description": "Reach level 10",
        "criteria": {"type": "level", "count": 10},
    },
    {
        "key": "streak_7",
        "name": "Week Warrior",
        "description": "Maintain a 7-day streak",
        "criteria": {"type": "streak_days", "count": 7},
    },
    {
        "key": "streak_30",
        "name": "Unstoppable",
        "description": "Maintain a 30-day streak",
        "criteria": {"type": "streak_days", "count": 30},
    },
]


async def ensure_first_admin(db: AsyncSession) -> None:
    """Create the first admin user from env settings if none exists."""
    existing = await db.execute(select(User).where(User.role == UserRole.ADMIN))
    if existing.scalar_one_or_none() is not None:
        return

    admin = User(
        email=settings.FIRST_ADMIN_EMAIL,
        username=settings.FIRST_ADMIN_USERNAME,
        full_name="Platform Administrator",
        hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.add(admin)
    await db.flush()
    print(f"✓ Created first admin user: {admin.email}")


async def ensure_default_badges(db: AsyncSession) -> None:
    """Create default badges if they don't already exist."""
    existing_keys = set(
        (await db.execute(select(Badge.key))).scalars().all()
    )

    created = 0
    for badge_data in DEFAULT_BADGES:
        if badge_data["key"] in existing_keys:
            continue
        db.add(Badge(**badge_data))
        created += 1

    if created:
        await db.flush()
        print(f"✓ Created {created} default badges")


async def run_seed(db: AsyncSession) -> None:
    """Run all seed operations."""
    await ensure_first_admin(db)
    await ensure_default_badges(db)
    await db.commit()
