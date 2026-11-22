"""FastAPI routes for verified direct Meta WhatsApp Cloud API webhooks."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

try:
    from ..app_config import ConfigurationError, WhatsAppSettings, get_whatsapp_settings
    from ..database import DATABASE_PATH
except ImportError:
    from app_config import ConfigurationError, WhatsAppSettings, get_whatsapp_settings
    from database import DATABASE_PATH

from .cloud_api import WhatsAppDeliveryError
from .cloud_api import (
    send_button_message, send_list_message, send_location_message, send_text_message,
)
from .conversation_service import process_incoming_message, record_ignored_message
from .message_templates import BotMessage


LOGGER = logging.getLogger(__name__)
router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])


def verify_meta_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    supplied = signature_header.removeprefix("sha256=").strip().lower()
    if len(supplied) != 64:
        return False
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)


def extract_messages(payload: dict[str, Any]) -> list[dict[str, str | None]]:
    """Flatten message notifications; status/read/delivery events yield no messages."""
    result: list[dict[str, str | None]] = []
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return result
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            value = change.get("value") or {}
            if not isinstance(value, dict):
                continue
            for message in value.get("messages") or []:
                if not isinstance(message, dict):
                    continue
                sender = message.get("from")
                message_id = message.get("id")
                message_type = message.get("type")
                content = None
                if message_type == "text":
                    content = (message.get("text") or {}).get("body")
                elif message_type == "interactive":
                    interactive = message.get("interactive") or {}
                    reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
                    content = reply.get("id") or reply.get("title")
                if sender and message_id:
                    result.append({
                        "sender": str(sender), "message_id": str(message_id),
                        "content": str(content) if content is not None else None,
                        "type": str(message_type or "unknown"),
                    })
    return result


async def dispatch_bot_message(
    recipient: str,
    message: BotMessage,
    *,
    settings: WhatsAppSettings,
    client: httpx.AsyncClient,
) -> None:
    kwargs = {"settings": settings, "client": client}
    if message.kind == "text":
        await send_text_message(recipient, message.text, **kwargs)
    elif message.kind == "buttons":
        await send_button_message(recipient, message.text, list(message.buttons), **kwargs)
    elif message.kind == "list":
        await send_list_message(recipient, message.text, list(message.rows), **kwargs)
    elif message.kind == "location" and message.latitude is not None and message.longitude is not None:
        await send_location_message(
            recipient, message.latitude, message.longitude,
            name=message.name or "Analytical reference",
            address=message.address or message.text,
            **kwargs,
        )


def _sender_log_hint(sender: str) -> str:
    digits = "".join(character for character in sender if character.isdigit())
    return f"***{digits[-2:]}" if digits else "***"


def _message_log_hint(message_id: str) -> str:
    return hashlib.sha256(message_id.encode("utf-8")).hexdigest()[:12]


def _log_delivery_failure(
    sender: str,
    message_id: str,
    failure: WhatsAppDeliveryError,
) -> None:
    LOGGER.error(
        "WhatsApp reply delivery failed sender=%s message_id_hash=%s http_status=%s "
        "graph_error_code=%s graph_error_subcode=%s graph_error_type=%s fbtrace_id=%s",
        _sender_log_hint(sender),
        _message_log_hint(message_id),
        failure.status_code,
        failure.graph_error_code,
        failure.graph_error_subcode,
        failure.graph_error_type,
        failure.fbtrace_id,
    )


async def _process_verified_messages(
    messages: list[dict[str, str | None]],
    settings: WhatsAppSettings,
) -> None:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for incoming in messages:
                sender = incoming["sender"]
                message_id = incoming["message_id"]
                try:
                    if incoming["content"] is None:
                        await run_in_threadpool(
                            record_ignored_message,
                            sender,
                            message_id,
                            database_path=DATABASE_PATH,
                        )
                        continue
                    result = await run_in_threadpool(
                        process_incoming_message,
                        sender,
                        incoming["content"],
                        message_id,
                        database_path=DATABASE_PATH,
                    )
                except ValueError:
                    LOGGER.warning(
                        "Ignored WhatsApp message with invalid sender metadata "
                        "message_id_hash=%s",
                        _message_log_hint(message_id),
                    )
                    continue
                except Exception as exc:
                    LOGGER.error(
                        "WhatsApp message processing failed sender=%s message_id_hash=%s "
                        "error_type=%s",
                        _sender_log_hint(sender),
                        _message_log_hint(message_id),
                        type(exc).__name__,
                    )
                    continue
                if result.duplicate:
                    continue
                for reply in result.replies:
                    try:
                        await dispatch_bot_message(
                            sender, reply, settings=settings, client=client
                        )
                    except WhatsAppDeliveryError as exc:
                        _log_delivery_failure(sender, message_id, exc)
                        break
                    except Exception as exc:
                        LOGGER.error(
                            "WhatsApp reply delivery failed sender=%s message_id_hash=%s "
                            "error_type=%s",
                            _sender_log_hint(sender),
                            _message_log_hint(message_id),
                            type(exc).__name__,
                        )
                        break
    except Exception as exc:
        LOGGER.error(
            "WhatsApp webhook background processing failed error_type=%s",
            type(exc).__name__,
        )


@router.get("/webhook", response_class=PlainTextResponse)
def verify_webhook(
    mode: str = Query(default="", alias="hub.mode"),
    verify_token: str = Query(default="", alias="hub.verify_token"),
    challenge: str = Query(default="", alias="hub.challenge"),
):
    try:
        settings = get_whatsapp_settings()
    except ConfigurationError as exc:
        raise HTTPException(503, "WhatsApp integration is not configured") from exc
    if mode != "subscribe" or not hmac.compare_digest(verify_token, settings.verify_token):
        raise HTTPException(403, "Webhook verification failed")
    return challenge


@router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        settings = get_whatsapp_settings()
    except ConfigurationError as exc:
        raise HTTPException(503, "WhatsApp integration is not configured") from exc
    raw_body = await request.body()
    if not verify_meta_signature(
        raw_body, request.headers.get("x-hub-signature-256"), settings.meta_app_secret
    ):
        raise HTTPException(401, "Invalid webhook signature")
    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, "Invalid webhook payload") from exc
    if not isinstance(payload, dict):
        raise HTTPException(400, "Invalid webhook payload")
    messages = extract_messages(payload)
    if messages:
        background_tasks.add_task(_process_verified_messages, messages, settings)
    return {"status": "ok", "accepted": len(messages)}
