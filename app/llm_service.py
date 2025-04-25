"""
LLM Service Module
Thin wrapper around the OpenAI ChatCompletion endpoint (openai-python 0.28.*).

The service turns a cleaned-up email body into a concise, friendly reply.
"""

from __future__ import annotations  # ← must be the first executable statement

# --------------------------------------------------------------------------- #
# Standard & 3-rd-party imports
# --------------------------------------------------------------------------- #
import os
from pathlib import Path
from typing import Final

from dotenv import load_dotenv
import openai

# --------------------------------------------------------------------------- #
# Environment setup
# --------------------------------------------------------------------------- #
# Load variables from the project-root .env file
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

openai.api_key = os.getenv("OPENAI_API_KEY", "").strip()

# --------------------------------------------------------------------------- #
# Constants (change these if you like)
# --------------------------------------------------------------------------- #
_DEFAULT_MODEL: Final[str] = "gpt-3.5-turbo"    # or "gpt-4o" if your key allows
_SYSTEM_PROMPT: Final[str] = (
    "You are Jack, a friendly senior ER doctor & entrepreneur. "
    "Write concise, helpful, professional replies."
)

# --------------------------------------------------------------------------- #
# Service class
# --------------------------------------------------------------------------- #
class LLMService:
    """Generate email replies with OpenAI ChatCompletion."""

    def __init__(
        self,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.model = model or _DEFAULT_MODEL
        self.system_prompt = system_prompt or _SYSTEM_PROMPT

    # ------------------------------------------------------------------ #
    #  Public API used by the rest of the application
    # ------------------------------------------------------------------ #
    def draft_reply(self, clean_email: str) -> str:
        """
        Return a reply to *clean_email*.

        Falls back to a canned sentence if the OpenAI call fails so the
        pipeline never crashes.
        """
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user",   "content": clean_email},
                ],
                temperature=0.5,
                max_tokens=300,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            print(f"[LLMService] OpenAI error → {exc}")
            return "I received your email and will get back to you soon."

    # ------------------------------------------------------------------ #
    #  Helpers for runtime tuning
    # ------------------------------------------------------------------ #
    def set_model(self, model_name: str) -> None:
        """Switch to a different OpenAI model (e.g. gpt-4o)."""
        self.model = model_name

    def update_system_prompt(self, new_prompt: str) -> None:
        """Replace the system prompt that guides the assistant’s style."""
        self.system_prompt = new_prompt
