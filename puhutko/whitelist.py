from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

import os


class WhitelistFilter(BaseFilter):
    def __init__(self):
        self.allowed_ids = (
            [int(id) for id in whitelist.split(",")]
            if (whitelist := os.environ.get("WHITELIST"))
            else []
        )

    async def __call__(self, obj: Message | CallbackQuery) -> bool:
        if isinstance(obj, Message):
            if obj.from_user is None:
                return False
            user_id = obj.from_user.id
        elif isinstance(obj, CallbackQuery):
            user_id = obj.from_user.id
        else:
            return False

        return user_id in self.allowed_ids
