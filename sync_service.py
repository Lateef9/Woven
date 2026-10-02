"""
Optional scheduled / manual sync into the ingest pipeline.

SYNC_INTERVAL_SECONDS=0 (default) disables the scheduler.
BOT_MODE=slack + Slack token → pull new Slack history per known channel.
Otherwise → generate one mock thread server-side and ingest (does not clear stores).
Set SYNC_MOCK_VIA_BOT=1 to call the Node bot /trigger-mock instead (clears stores).
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

from database import db_manager
from ingest_service import ingest_message
from schemas import Message

load_dotenv()

_scheduler = None
_sync_lock = asyncio.Lock()
_last_run: dict[str, Any] | None = None
_last_run_at: str | None = None


def get_sync_interval_seconds() -> int:
    raw = os.getenv("SYNC_INTERVAL_SECONDS", "0") or "0"
    try:
        return max(0, int(raw))
    except ValueError:
        print(f"Invalid SYNC_INTERVAL_SECONDS={raw!r}; treating as 0 (disabled).")
        return 0


def resolve_sync_mode() -> str:
    forced = (os.getenv("BOT_MODE") or "").strip().lower()
    if forced in ("mock", "slack"):
        return forced
    if os.getenv("SLACK_BOT_TOKEN"):
        return "slack"
    return "mock"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def generate_mock_thread() -> list[Message]:
    """Server-side mock weekend-plans thread (does not clear stores)."""
    channel_id = str(uuid.uuid4())
    channel_name = "weekend-plans"
    now = _utcnow()

    maya = {"user_id": str(uuid.uuid4()), "name": "Maya", "platform": "mock"}
    jordan = {"user_id": str(uuid.uuid4()), "name": "Jordan", "platform": "mock"}
    sam = {"user_id": str(uuid.uuid4()), "name": "Sam", "platform": "mock"}
    channel = {"channel_id": channel_id, "name": channel_name, "platform": "mock"}

    rows = [
        (maya, "Anyone free this Saturday? I was thinking we finally do that coastal trip to Goa.", 400),
        (jordan, "I'm in! Let's stay near Anjuna Beach. I found a place called Sea Breeze Homestay for about 2500 a night.", 300),
        (sam, "Perfect. I can book the IndiGo flight leaving Friday evening from Bangalore.", 200),
        (maya, "Also, dinner at Britto's on Saturday night? They do great seafood and live music.", 100),
        (jordan, "Done. Jordan handles the homestay, Sam books flights, Maya reserves Britto's. Can't wait!", 0),
    ]

    messages: list[Message] = []
    for author, text, ago_sec in rows:
        messages.append(
            Message(
                message_id=str(uuid.uuid4()),
                text=text,
                timestamp=now - timedelta(seconds=ago_sec),
                author=author,
                channel=channel,
            )
        )
    return messages


async def _sync_mock_via_bot() -> dict[str, Any]:
    bot_url = (os.getenv("BOT_URL") or "http://localhost:3001").rstrip("/")
    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.get(f"{bot_url}/trigger-mock")
        res.raise_for_status()
        body = res.json()
    return {
        "mode": "mock",
        "via": "bot_trigger_mock",
        "messages_ingested": int(body.get("messages_sent") or 0),
        "channels_ok": 1,
        "channels_failed": 0,
        "errors": [],
        "status": "ok",
        "bot_response": body,
    }


async def _sync_mock_server_side() -> dict[str, Any]:
    messages = generate_mock_thread()
    ingested = 0
    errors: list[dict[str, str]] = []
    channel_id = messages[0].channel.channel_id if messages else ""

    for msg in messages:
        try:
            await ingest_message(msg)
            ingested += 1
        except Exception as e:
            print(f"Mock sync ingest failed for {msg.message_id}: {e}")
            errors.append({"channel_id": channel_id, "error": str(e)})

    if channel_id:
        try:
            await db_manager.channels.update_one(
                {"channel_id": channel_id},
                {
                    "$set": {
                        "channel_id": channel_id,
                        "name": messages[0].channel.name,
                        "platform": "mock",
                        "last_sync_ts": _isoformat(_utcnow()),
                        "last_sync_at": _utcnow(),
                    }
                },
                upsert=True,
            )
        except Exception as e:
            print(f"Failed to persist last_sync_ts for mock channel: {e}")
            errors.append({"channel_id": channel_id, "error": f"last_sync_ts: {e}"})

    status = "ok" if not errors else ("partial" if ingested else "error")
    return {
        "mode": "mock",
        "via": "server_side",
        "messages_ingested": ingested,
        "channels_ok": 1 if ingested else 0,
        "channels_failed": 1 if status == "error" else 0,
        "errors": errors,
        "status": status,
    }


async def _slack_user_name(client: httpx.AsyncClient, token: str, user_id: str, cache: dict[str, str]) -> str:
    if not user_id:
        return "unknown"
    if user_id in cache:
        return cache[user_id]
    try:
        res = await client.get(
            "https://slack.com/api/users.info",
            headers={"Authorization": f"Bearer {token}"},
            params={"user": user_id},
        )
        data = res.json()
        if data.get("ok"):
            user = data.get("user") or {}
            profile = user.get("profile") or {}
            name = (
                profile.get("display_name")
                or user.get("real_name")
                or user.get("name")
                or user_id
            )
            cache[user_id] = name
            return name
    except Exception as e:
        print(f"Slack users.info failed for {user_id}: {e}")
    cache[user_id] = user_id
    return user_id


def _is_ingestible_slack_message(msg: dict) -> bool:
    if msg.get("bot_id") or msg.get("subtype"):
        return False
    text = (msg.get("text") or "").strip()
    return bool(text)


async def _fetch_slack_history(
    client: httpx.AsyncClient,
    token: str,
    channel_id: str,
    oldest: str | None,
    limit: int = 100,
) -> list[dict]:
    params: dict[str, Any] = {"channel": channel_id, "limit": limit}
    if oldest:
        params["oldest"] = oldest
        params["inclusive"] = False

    res = await client.get(
        "https://slack.com/api/conversations.history",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )
    data = res.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error") or "conversations.history failed")
    # Slack returns newest-first; ingest oldest-first for stable ordering
    messages = list(data.get("messages") or [])
    messages.reverse()
    return messages


async def _sync_one_slack_channel(
    client: httpx.AsyncClient,
    token: str,
    channel: dict,
    user_cache: dict[str, str],
) -> dict[str, Any]:
    channel_id = channel.get("channel_id") or ""
    channel_name = channel.get("name") or channel_id
    last_sync_ts = channel.get("last_sync_ts")
    if isinstance(last_sync_ts, datetime):
        last_sync_ts = str(last_sync_ts.timestamp())

    oldest = str(last_sync_ts) if last_sync_ts else None
    raw_messages = await _fetch_slack_history(client, token, channel_id, oldest)
    ingested = 0
    newest_ts: str | None = oldest

    for raw in raw_messages:
        if not _is_ingestible_slack_message(raw):
            # Still advance watermark past skipped messages so we don't re-fetch forever
            ts = raw.get("ts")
            if ts and (newest_ts is None or float(ts) > float(newest_ts)):
                newest_ts = str(ts)
            continue

        ts = str(raw.get("ts") or "")
        user_id = raw.get("user") or "unknown"
        author_name = await _slack_user_name(client, token, user_id, user_cache)
        message_id = raw.get("client_msg_id") or f"{channel_id}:{ts}"

        try:
            ts_float = float(ts) if ts else _utcnow().timestamp()
            timestamp = datetime.fromtimestamp(ts_float, tz=timezone.utc)
        except ValueError:
            timestamp = _utcnow()

        msg = Message(
            message_id=message_id,
            text=(raw.get("text") or "").strip(),
            timestamp=timestamp,
            author={"user_id": user_id, "name": author_name, "platform": "slack"},
            channel={
                "channel_id": channel_id,
                "name": channel_name,
                "platform": "slack",
            },
        )
        await ingest_message(msg)
        ingested += 1
        if ts and (newest_ts is None or float(ts) > float(newest_ts)):
            newest_ts = str(ts)

    if newest_ts and newest_ts != oldest:
        await db_manager.channels.update_one(
            {"channel_id": channel_id},
            {
                "$set": {
                    "channel_id": channel_id,
                    "name": channel_name,
                    "platform": channel.get("platform") or "slack",
                    "last_sync_ts": newest_ts,
                    "last_sync_at": _utcnow(),
                }
            },
            upsert=True,
        )
    elif not oldest:
        # No messages / nothing new — stamp "now" so the next run only fetches newer
        await db_manager.channels.update_one(
            {"channel_id": channel_id},
            {
                "$set": {
                    "last_sync_at": _utcnow(),
                    "last_sync_ts": channel.get("last_sync_ts")
                    or f"{_utcnow().timestamp():.6f}",
                }
            },
            upsert=True,
        )

    return {
        "channel_id": channel_id,
        "messages_ingested": ingested,
        "last_sync_ts": newest_ts,
    }


async def _list_known_channels() -> list[dict]:
    try:
        docs = await db_manager.channels.find(
            {},
            {
                "_id": 0,
                "channel_id": 1,
                "name": 1,
                "platform": 1,
                "last_sync_ts": 1,
                "last_sync_at": 1,
            },
        ).to_list(length=500)
        return [d for d in docs if d.get("channel_id")]
    except Exception as e:
        print(f"Error listing channels for sync: {e}")
        return []


async def _sync_slack() -> dict[str, Any]:
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        return {
            "mode": "slack",
            "messages_ingested": 0,
            "channels_ok": 0,
            "channels_failed": 0,
            "errors": [{"channel_id": "*", "error": "SLACK_BOT_TOKEN not set"}],
            "status": "error",
        }

    channels = await _list_known_channels()
    slack_channels = [
        c for c in channels
        if (c.get("platform") or "").lower() == "slack" or not c.get("platform")
    ]
    # Prefer explicitly slack; if none tagged, use all known channel ids
    if not slack_channels:
        slack_channels = channels

    if not slack_channels:
        return {
            "mode": "slack",
            "messages_ingested": 0,
            "channels_ok": 0,
            "channels_failed": 0,
            "errors": [],
            "status": "ok",
            "note": "No known channels in Mongo yet. Invite the bot and ingest once, or wait for live events.",
        }

    messages_ingested = 0
    channels_ok = 0
    channels_failed = 0
    errors: list[dict[str, str]] = []
    user_cache: dict[str, str] = {}

    async with httpx.AsyncClient(timeout=60.0) as client:
        for channel in slack_channels:
            channel_id = channel.get("channel_id") or "?"
            try:
                result = await _sync_one_slack_channel(client, token, channel, user_cache)
                messages_ingested += int(result.get("messages_ingested") or 0)
                channels_ok += 1
            except Exception as e:
                channels_failed += 1
                print(f"Sync failed for channel {channel_id}: {e}")
                errors.append({"channel_id": channel_id, "error": str(e)})

    if channels_failed and channels_ok:
        status = "partial"
    elif channels_failed and not channels_ok:
        status = "error"
    else:
        status = "ok"

    return {
        "mode": "slack",
        "messages_ingested": messages_ingested,
        "channels_ok": channels_ok,
        "channels_failed": channels_failed,
        "errors": errors,
        "status": status,
    }


async def run_sync(*, force: bool = False) -> dict[str, Any]:
    """
    Run one sync cycle. Failures for individual channels are isolated.
    """
    global _last_run, _last_run_at

    if _sync_lock.locked() and not force:
        return {
            "status": "skipped",
            "reason": "sync already running",
            "last_run_at": _last_run_at,
            "last_run": _last_run,
        }

    async with _sync_lock:
        mode = resolve_sync_mode()
        print(f"Starting sync run mode={mode}")
        try:
            if mode == "slack":
                result = await _sync_slack()
            elif (os.getenv("SYNC_MOCK_VIA_BOT") or "").strip() in ("1", "true", "yes"):
                try:
                    result = await _sync_mock_via_bot()
                except Exception as e:
                    print(f"Bot /trigger-mock failed, falling back to server-side mock: {e}")
                    result = await _sync_mock_server_side()
                    result["bot_trigger_error"] = str(e)
            else:
                result = await _sync_mock_server_side()
        except Exception as e:
            print(f"Sync run failed: {e}")
            result = {
                "mode": mode,
                "messages_ingested": 0,
                "channels_ok": 0,
                "channels_failed": 0,
                "errors": [{"channel_id": "*", "error": str(e)}],
                "status": "error",
            }

        _last_run_at = _isoformat(_utcnow())
        _last_run = result
        print(
            f"Sync finished status={result.get('status')} "
            f"messages={result.get('messages_ingested')} "
            f"ok={result.get('channels_ok')} failed={result.get('channels_failed')}"
        )
        return {
            "last_run_at": _last_run_at,
            **result,
        }


async def get_sync_status() -> dict[str, Any]:
    interval = get_sync_interval_seconds()
    channels = await _list_known_channels()
    channel_status = [
        {
            "channel_id": c.get("channel_id"),
            "name": c.get("name"),
            "platform": c.get("platform"),
            "last_sync_ts": c.get("last_sync_ts"),
            "last_sync_at": _isoformat(c["last_sync_at"])
            if isinstance(c.get("last_sync_at"), datetime)
            else c.get("last_sync_at"),
        }
        for c in channels
    ]
    return {
        "enabled": interval > 0,
        "interval_seconds": interval,
        "mode": resolve_sync_mode(),
        "scheduler_running": bool(_scheduler and _scheduler.running),
        "last_run_at": _last_run_at,
        "last_run": _last_run,
        "channels": channel_status,
    }


def start_scheduler():
    """Start APScheduler interval job when SYNC_INTERVAL_SECONDS > 0."""
    global _scheduler
    interval = get_sync_interval_seconds()
    if interval <= 0:
        print("Scheduled sync disabled (SYNC_INTERVAL_SECONDS=0).")
        return None

    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_sync,
        trigger="interval",
        seconds=interval,
        id="woven_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=interval,
    )
    _scheduler.start()
    print(f"Scheduled sync enabled: every {interval}s (mode={resolve_sync_mode()})")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("Scheduled sync stopped.")
    _scheduler = None
