"""Data models for the Propos reply engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TonePreference(Enum):
    WARM_FRIENDLY = "warm_friendly"
    PROFESSIONAL = "professional"
    ENTHUSIASTIC = "enthusiastic"
    RELAXED_CASUAL = "relaxed_casual"


TONE_DESCRIPTIONS = {
    TonePreference.WARM_FRIENDLY: (
        "Conversational and approachable. Feels like a local business "
        "with genuine personality. Warm but not over the top."
    ),
    TonePreference.PROFESSIONAL: (
        "Polished and courteous. Considered and measured. "
        "Suits hotels and fine dining."
    ),
    TonePreference.ENTHUSIASTIC: (
        "High energy and extra grateful. Suits cafes and casual eateries."
    ),
    TonePreference.RELAXED_CASUAL: (
        "Laid-back and informal. Like a reply from the owner themselves. "
        "Suits bars and pubs."
    ),
}


@dataclass
class Review:
    reviewer_name: str
    star_rating: int  # 1-5
    review_text: str  # may be empty for star-only reviews
    review_id: Optional[str] = None


@dataclass
class BusinessProfile:
    name: str
    business_type: str  # e.g. restaurant, cafe, hotel, bar
    city: str
    client_id: str
    owner_name: Optional[str] = None
    tone_preference: TonePreference = TonePreference.WARM_FRIENDLY


@dataclass
class ReplyResult:
    reply_text: str
    auto_post: bool
    routing_reason: str
    review: Review
    tone_used: TonePreference
    tone_memory_examples_used: int
    is_spam: bool = False
    low_confidence: bool = False
    confidence_reason: Optional[str] = None
