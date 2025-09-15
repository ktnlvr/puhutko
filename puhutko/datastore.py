from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from redis import asyncio as aioredis

from .card import Card

MAX_EVENT_LENGHT = 100000


class CardStats(BaseModel):
    num_cards: int
    avg_age_seconds: float
    oldest_age_seconds: float
    avg_reps: float


class Datastore:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = aioredis.from_url(redis_url)

    def _queue_key(self, user: int) -> str:
        return f"{user}:queue"

    def _card_key(self, user: int, card_id: int) -> str:
        return f"{user}:card:{card_id}"

    async def save_card(
        self, user: int, card: Card, next_due: Optional[datetime] = None
    ):
        key = self._card_key(user, card.card_id)
        await self.redis.set(key, card.model_dump_json())
        if next_due is not None:
            ts = int(next_due.timestamp())
            await self.redis.zadd(self._queue_key(user), {str(card.card_id): ts})

    async def get_card(self, user: int, card_id: int) -> Optional[Card]:
        data = await self.redis.get(self._card_key(user, card_id))
        if not data:
            return None
        return Card.model_validate_json(data)

    async def delete_card(self, user: int, card_id: int):
        await self.redis.delete(self._card_key(user, card_id))
        await self.redis.zrem(self._queue_key(user), card_id)

    async def get_due_cards(
        self, user: int, until: Optional[datetime] = None
    ) -> list[tuple[int, int]]:
        if until is None:
            until = datetime.now()
        ts = int(until.timestamp())
        entries = await self.redis.zrangebyscore(
            self._queue_key(user), min="-inf", max=ts, withscores=True
        )
        result = []
        for member, score in entries:
            try:
                cid = int(member)
            except ValueError:
                continue
            result.append((cid, int(score)))
        return result

    async def pop_one_due(
        self, user: int, cram: bool = False
    ) -> Optional[tuple[int, int]]:
        now_ts = int(datetime.now().timestamp())
        if cram:
            entries = await self.redis.zrange(
                self._queue_key(user), 0, 0, withscores=True
            )
        else:
            entries = await self.redis.zrangebyscore(
                self._queue_key(user),
                min="-inf",
                max=now_ts,
                start=0,
                num=1,
                withscores=True,
            )

        if not entries:
            return None
        member, score = entries[0]
        await self.redis.zrem(self._queue_key(user), member)
        return int(member), int(score)

    async def reschedule_card(self, user: int, card_id: int, next_due: datetime):
        ts = int(next_due.timestamp())
        await self.redis.zadd(self._queue_key(user), mapping={card_id: ts})  # type: ignore

    async def set_cram_mode(self, user: int, enabled: bool):
        key = f"user:{user}:is_cramming"
        if enabled:
            await self.redis.set(key, 1)
        else:
            await self.redis.delete(key)

    async def get_cram_mode(self, user: int) -> bool:
        key = f"user:{user}:cram_mode"
        val = await self.redis.get(key)
        return val == 1

    async def log_event(
        self,
        user: int,
        event: str,
        card_id: int | None = None,
        extra: dict | None = None,
    ):
        key = f"{user}:user:events"
        fields = {"timestamp": datetime.now().isoformat(), "event": event}
        if card_id is not None:
            fields["card_id"] = str(card_id)
        if extra:
            for k, v in extra.items():
                fields[k] = str(v)

        await self.redis.xadd(name=key, fields=fields, maxlen=MAX_EVENT_LENGHT, approximate=True)  # type: ignore

    async def stats(self, user: int) -> CardStats:
        pattern = f"{user}:card:*"
        keys = await self.redis.keys(pattern)
        if not keys:
            return CardStats(
                num_cards=0, avg_age_seconds=0.0, oldest_age_seconds=0.0, avg_reps=0.0
            )

        raws = await self.redis.mget(*keys)
        cards = []
        for raw in raws:
            if not raw:
                continue
            try:
                cards.append(Card.parse_raw(raw))
            except Exception:
                continue

        if not cards:
            return CardStats(
                num_cards=0, avg_age_seconds=0.0, oldest_age_seconds=0.0, avg_reps=0.0
            )

        now = datetime.now()
        ages = []
        total_reps = 0
        for c in cards:
            total_reps += c.repetitions
            if c.last_review:
                ages.append((now - c.last_review).total_seconds())

        avg_reps = total_reps / len(cards)
        avg_age = sum(ages) / len(ages) if ages else 0.0
        oldest = max(ages) if ages else 0.0

        return CardStats(
            num_cards=len(cards),
            avg_age_seconds=float(avg_age),
            oldest_age_seconds=float(oldest),
            avg_reps=float(avg_reps),
        )
