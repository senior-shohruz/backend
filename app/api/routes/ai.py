"""AI Teacher endpoint."""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.lesson import Lesson
from app.schemas.progress import AIAskRequest, AIAskResponse
from app.services.ai_teacher import ai_teacher

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/ask", response_model=AIAskResponse)
async def ask_ai_teacher(
    payload: AIAskRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AIAskResponse:
    """Ask the AI teacher a question, optionally about a specific lesson and student code."""
    lesson_context = None
    if payload.lesson_id is not None:
        lesson = (await db.execute(
            select(Lesson).where(Lesson.id == payload.lesson_id)
        )).scalar_one_or_none()
        if lesson is not None:
            lesson_context = f"Title: {lesson.title}\n\n{lesson.content[:2000]}"

    code = payload.code_context
    answer = await ai_teacher.ask(
        question=payload.question,
        lesson_context=lesson_context,
        code_html=code.html if code else None,
        code_css=code.css if code else None,
        code_js=code.js if code else None,
    )

    return AIAskResponse(answer=answer, lesson_id=payload.lesson_id)
