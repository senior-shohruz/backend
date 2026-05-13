"""AI Teacher service — Groq (fastest free AI)."""
from typing import Optional
import httpx

from app.core.config import settings

SYSTEM_PROMPT = """You are an expert AI Frontend Teacher on an interactive learning platform. 
You help students learn HTML, CSS, JavaScript, and React.

IMPORTANT RULES:
- Always read the question carefully and give a SPECIFIC answer
- Always include practical code examples
- Be encouraging and friendly
- Keep responses clear and under 400 words
- If code has errors, point out EXACTLY what is wrong and provide fixed code
- Answer in the same language the student uses (Uzbek, Russian, or English)"""


class AITeacherService:
    def __init__(self) -> None:
        self.api_key = settings.ANTHROPIC_API_KEY

    async def ask(
        self,
        question: str,
        lesson_context: Optional[str] = None,
        code_html: Optional[str] = None,
        code_css: Optional[str] = None,
        code_js: Optional[str] = None,
    ) -> str:
        if not self.api_key:
            return "AI Teacher is not configured."

        context_parts = []
        if lesson_context:
            context_parts.append(f"Current lesson context:\n{lesson_context}")
        if code_html:
            context_parts.append(f"Student's HTML code:\n```html\n{code_html}\n```")
        if code_css:
            context_parts.append(f"Student's CSS code:\n```css\n{code_css}\n```")
        if code_js:
            context_parts.append(f"Student's JavaScript code:\n```javascript\n{code_js}\n```")

        context_str = "\n\n".join(context_parts)
        user_message = (
            f"Context:\n{context_str}\n\nStudent's question: {question}"
            if context_str
            else f"Student's question: {question}"
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_message},
                        ],
                        "max_tokens": 1024,
                        "temperature": 0.7,
                    },
                    timeout=15.0,
                )
                data = response.json()
                if "choices" in data:
                    return data["choices"][0]["message"]["content"]
                else:
                    return f"Error: {data.get('error', {}).get('message', 'Unknown error')}"
        except httpx.TimeoutException:
            return "Sorry, the request timed out. Please try again."
        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"


ai_teacher = AITeacherService()