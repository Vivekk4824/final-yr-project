"""Minimal direct client for Meta WhatsApp Cloud API message delivery."""
from __future__ import annotations

import re
from typing import Any

import httpx

try:
    from ..app_config import WhatsAppSettings, get_whatsapp_settings
except ImportError:
    from app_config import WhatsAppSettings, get_whatsapp_settings


class WhatsAppDeliveryError(RuntimeError):
    """Safe delivery failure that never includes credentials or response bodies."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        graph_error_code: int | None = None,
        graph_error_subcode: int | None = None,
        graph_error_type: str | None = None,
        fbtrace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.graph_error_code = graph_error_code
        self.graph_error_subcode = graph_error_subcode
        self.graph_error_type = graph_error_type
        self.fbtrace_id = fbtrace_id


def _endpoint(settings: WhatsAppSettings) -> str:
    return (
        f"https://graph.facebook.com/{settings.graph_version}/"
        f"{settings.phone_number_id}/messages"
    )


def _graph_error_metadata(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    if not isinstance(body, dict) or not isinstance(body.get("error"), dict):
        return {}
    error = body["error"]
    metadata: dict[str, Any] = {}
    for source, target in (
        ("code", "graph_error_code"),
        ("error_subcode", "graph_error_subcode"),
    ):
        value = error.get(source)
        if isinstance(value, int) and not isinstance(value, bool):
            metadata[target] = value
    for source, target in (("type", "graph_error_type"), ("fbtrace_id", "fbtrace_id")):
        value = error.get(source)
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value):
            metadata[target] = value
    return metadata


async def _send_payload(
    recipient: str,
    message: dict[str, Any],
    *,
    settings: WhatsAppSettings | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    settings = settings or get_whatsapp_settings()
    payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": recipient, **message}
    headers = {
        "Authorization": f"Bearer {settings.access_token}",
        "Content-Type": "application/json",
    }
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=15.0)
    try:
        response = await active_client.post(_endpoint(settings), headers=headers, json=payload)
        if response.status_code >= 400:
            raise WhatsAppDeliveryError(
                f"Meta WhatsApp delivery failed with HTTP {response.status_code}",
                status_code=response.status_code,
                **_graph_error_metadata(response),
            )
        try:
            result = response.json()
        except ValueError:
            raise WhatsAppDeliveryError(
                "Meta WhatsApp returned an invalid response",
                status_code=response.status_code,
            ) from None
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("messages"), list)
            or not any(
                isinstance(item, dict) and isinstance(item.get("id"), str)
                for item in result["messages"]
            )
        ):
            raise WhatsAppDeliveryError(
                "Meta WhatsApp returned an unexpected response",
                status_code=response.status_code,
                **_graph_error_metadata(response),
            )
        return result
    except httpx.HTTPError:
        raise WhatsAppDeliveryError("Meta WhatsApp delivery request failed") from None
    finally:
        if owns_client:
            await active_client.aclose()


async def send_text_message(recipient: str, text: str, **kwargs) -> dict[str, Any]:
    return await _send_payload(recipient, {"type": "text", "text": {"preview_url": False, "body": text}}, **kwargs)


async def send_button_message(
    recipient: str,
    body: str,
    buttons: list[tuple[str, str]],
    **kwargs,
) -> dict[str, Any]:
    action = {"buttons": [
        {"type": "reply", "reply": {"id": button_id[:256], "title": title[:20]}}
        for button_id, title in buttons[:3]
    ]}
    return await _send_payload(recipient, {
        "type": "interactive",
        "interactive": {"type": "button", "body": {"text": body[:1024]}, "action": action},
    }, **kwargs)


async def send_list_message(
    recipient: str,
    body: str,
    rows: list[tuple[str, str, str]],
    *,
    button_label: str = "Choose",
    **kwargs,
) -> dict[str, Any]:
    action = {
        "button": button_label[:20],
        "sections": [{"title": "Options", "rows": [
            {"id": row_id[:200], "title": title[:24], "description": description[:72]}
            for row_id, title, description in rows[:10]
        ]}],
    }
    return await _send_payload(recipient, {
        "type": "interactive",
        "interactive": {"type": "list", "body": {"text": body[:1024]}, "action": action},
    }, **kwargs)


async def send_location_message(
    recipient: str,
    latitude: float,
    longitude: float,
    *,
    name: str,
    address: str,
    **kwargs,
) -> dict[str, Any]:
    return await _send_payload(recipient, {
        "type": "location",
        "location": {
            "latitude": latitude, "longitude": longitude,
            "name": name[:1000], "address": address[:1000],
        },
    }, **kwargs)
