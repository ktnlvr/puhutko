from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .snowflake import snowflake


class Card(BaseModel):
    card_id: int
    last_review: Optional[datetime]
    repetitions: int
    interval: int
    ease_factor: float

    front: str
    back: str

    can_flip: bool

    @staticmethod
    def simple(front: str, back: str, can_flip: bool) -> "Card":
        card_id = snowflake()

        return Card(
            card_id=card_id,
            last_review=None,
            repetitions=0,
            interval=0,
            ease_factor=2.5,
            front=front,
            back=back,
            can_flip=can_flip,
        )
