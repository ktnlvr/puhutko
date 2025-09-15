from . import BOT, dp, asyncio


async def main():
    try:
        print("Bot started. Polling...")
        await dp.start_polling(BOT)
    finally:
        await BOT.session.close()


if __name__ == "__main__":
    asyncio.run(main())
