import asyncio
import json
import os
import signal
from datetime import datetime, timedelta, timezone

import aiohttp
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from discord import Embed, Webhook
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.helper import first
from twitchAPI.object.api import Clip
from twitchAPI.object.eventsub import StreamOnlineEvent
from twitchAPI.twitch import Twitch, TwitchUser

load_dotenv(override=True)
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
TWITCH_USERNAME = os.getenv("TWITCH_USERNAME")
TWITCH_INBOUND_URL = os.getenv("TWITCH_INBOUND_URL")
DISCORD_STREAMS_WEBHOOK_URL = os.getenv("DISCORD_STREAMS_WEBHOOK_URL")
DISCORD_CLIPS_WEBHOOK_URL = os.getenv("DISCORD_CLIPS_WEBHOOK_URL")
LOCAL_PORT = int(os.getenv("LOCAL_PORT"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TIMEZONE = os.getenv("TIMEZONE")
EMOJI_STRING = os.getenv("EMOJI_STRING")


# current file's directory
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
# newline-separated file of clip IDs we've already posted, since Twitch can't reliably filter by date
CACHE_FILE_PATH = os.path.join(__location__, "posted_clips.txt")
# ensure the cache file exists
with open(CACHE_FILE_PATH, "a+") as f:
    pass


### STREAM SECTION
# generate a stream announcement
async def generate_stream_announcement():
    twitch = await Twitch(TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)
    user = await first(twitch.get_users(logins=TWITCH_USERNAME))
    channels = await twitch.get_channel_information(user.id)
    channel = channels[0] if len(channels) > 0 else None
    data_dict = {
        "current_datetime": datetime.now(pytz.utc)
        .astimezone(pytz.timezone("America/Halifax"))
        .isoformat(),
        "user_display_name": user.display_name,
        "user_created_at": user.created_at.astimezone(
            pytz.timezone("America/Halifax")
        ).isoformat(),
        "user_broadcaster_type": user.broadcaster_type,
        "user_description": user.description,
    }
    if channel:
        data_dict.update(
            {
                "channel_message_of_the_day": channel.title,
                "channel_game": channel.game_name,
                "channel_tags": channel.tags,
            }
        )
    prompt = f"""Write a long announcement that a Twitch streamer is beginning a stream.
It should be in third-person.
This is for the streamer's discord fan server, so no need to introduce him or give a ton of details.
For example, no need to share his whole PC specs. Maybe reference current events, weather, etc.
Use many of the following emojis and stock ones, at least one per sentence: {EMOJI_STRING}

All info:

{json.dumps(data_dict)}"""

    print("Prompt:\n\n", prompt)
    client = OpenAI()
    announcement = (
        f"{user.display_name} is now live!\nhttps://twitch.tv/{TWITCH_USERNAME}"
    )
    try:
        response = client.responses.create(model="gpt-4.1-nano", input=prompt)
        announcement = f"{response.output_text}\nhttps://twitch.tv/{TWITCH_USERNAME}"
    except RateLimitError as e:
        print("RateLimitError", e)
    except Exception as E:
        print("Exception", e)

    print("Response:\n\n", announcement)

    return announcement


# post a stream announcement
async def post_stream_announcement(announcement: str):
    async with aiohttp.ClientSession() as session:
        webhook = Webhook.from_url(DISCORD_STREAMS_WEBHOOK_URL, session=session)
        await webhook.send(announcement)


# post to discord when a stream online event occurs
async def on_stream_start(data: StreamOnlineEvent):
    print(f"{data.event.broadcaster_user_name} is live!")
    announcement = await generate_stream_announcement()
    await post_stream_announcement(announcement)


# capture stream online events
async def stream_listener(shutdown_event: asyncio.Event):
    if not bool(DISCORD_STREAMS_WEBHOOK_URL):
        return
    twitch = await Twitch(TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)
    print("USERNAME", TWITCH_USERNAME)
    user = await first(twitch.get_users(logins=TWITCH_USERNAME))
    eventsub = EventSubWebhook(TWITCH_INBOUND_URL, LOCAL_PORT, twitch)
    # unsubscribe from any old events to ensure clean slate
    await eventsub.unsubscribe_all()
    eventsub.start()
    await eventsub.listen_stream_online(user.id, on_stream_start)

    try:
        await shutdown_event.wait()
    finally:
        # stopping both eventsub as well as gracefully closing the connection to the API
        await eventsub.stop()
        await twitch.close()


### CLIPS SECTION
async def get_clips_loop(shutdown_event: asyncio.Event):
    if not bool(DISCORD_CLIPS_WEBHOOK_URL):
        return
    while not shutdown_event.is_set():
        try:
            await get_clips()
        except Exception as e:
            print(f"[ERROR] get_clips failed: {e}")
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass  # timeout expired, continue loop


async def get_clips():
    print("Checking for new clips...")
    twitch = await Twitch(TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)
    user = await first(twitch.get_users(logins=TWITCH_USERNAME))
    clips = twitch.get_clips(user.id, started_at=datetime.now() - timedelta(hours=1))
    clip_ids = []
    with open(CACHE_FILE_PATH, "r") as f:
        clip_ids = f.readlines()
    print("existing clip ids", clip_ids)
    new_clips: list[Clip] = []
    # filter clips
    async for clip in clips:
        clip_id_newline = f"{clip.id}\n"
        if clip_id_newline not in clip_ids:
            print("new clip", clip.id)
            clip_ids.append(clip_id_newline)
            new_clips.append(clip)
        else:
            print("old clip", clip.id)
    with open(CACHE_FILE_PATH, "w") as f:
        f.writelines(clip_ids)
    # send new clips to discord
    async with aiohttp.ClientSession() as session:
        for clip in new_clips:
            webhook = Webhook.from_url(DISCORD_CLIPS_WEBHOOK_URL, session=session)
            await webhook.send(
                embed=Embed(
                    title=clip.title,
                    url=clip.url,
                    timestamp=clip.created_at,
                    description=f"New clip by {clip.creator_name}",
                ).set_image(url=clip.thumbnail_url)
            )
    print("Done checking for new clips")


async def main():
    shutdown_event = asyncio.Event()

    def handle_signal():
        print("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)
    await asyncio.gather(
        stream_listener(shutdown_event), get_clips_loop(shutdown_event)
    )


if __name__ == "__main__":
    asyncio.run(main())
