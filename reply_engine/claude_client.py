"""Claude API client for the Propos reply engine."""

import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    raise EnvironmentError(
        "ANTHROPIC_API_KEY environment variable is not set. "
        "Set it with: export ANTHROPIC_API_KEY=your_key"
    )

MODEL = "claude-sonnet-4-5-20250929"
_client = Anthropic(api_key=API_KEY)


def generate_reply(system_prompt: str, user_prompt: str) -> str:
    """Generate a review reply using Claude."""
    message = _client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text.strip()


def classify(system_prompt: str, user_prompt: str) -> str:
    """Lightweight Claude call for classification tasks (sentiment, spam, confidence)."""
    message = _client.messages.create(
        model=MODEL,
        max_tokens=50,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text.strip().lower()
