import asyncio

import twitch_update_bot


async def generate_and_post():
    announcement = await twitch_update_bot.generate_stream_announcement()
    await twitch_update_bot.post_stream_announcement(announcement)


if __name__ == "__main__":
    asyncio.run(generate_and_post())
