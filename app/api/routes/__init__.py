"""API routes — combine all sub-routers into one main router."""
from fastapi import APIRouter

from app.api.routes import auth, courses, quiz, progress, ai, admin

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(courses.router)
api_router.include_router(quiz.router)
api_router.include_router(progress.router)
api_router.include_router(ai.router)
api_router.include_router(admin.router)
