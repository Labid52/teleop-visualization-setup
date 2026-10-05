#!/usr/bin/env python3
"""Authenticated, latest-state WebSocket relay for visualization telemetry."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import signal
import ssl
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed


LOGGER = logging.getLogger("teleop-telemetry")
MAX_MESSAGE_BYTES = 65_536
AUTH_TIMEOUT_SECONDS = 5.0
SUBSCRIBER_SEND_TIMEOUT_SECONDS = 2.0
EXPECTED_MESSAGE_TYPE = "vehicle_visualization"


class ProtocolError(ValueError):
    pass


def decode_json(raw: str | bytes) -> dict[str, Any]:
    if isinstance(raw, bytes):
        if len(raw) > MAX_MESSAGE_BYTES:
            raise ProtocolError("message too large")
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("message is not UTF-8") from exc
    if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message too large")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProtocolError("invalid JSON") from exc
    if not isinstance(value, dict):
        raise ProtocolError("message must be a JSON object")
    return value


def validate_telemetry(raw: str | bytes) -> str:
    value = decode_json(raw)
    if value.get("schema_version") != 1:
        raise ProtocolError("unsupported schema_version")
    if value.get("message_type") != EXPECTED_MESSAGE_TYPE:
        raise ProtocolError("unsupported message_type")
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


@dataclass(eq=False)
class Subscriber:
    connection: ServerConnection
    queue: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(maxsize=1))

    def replace_latest(self, message: str) -> None:
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self.queue.put_nowait(message)


class TelemetryHub:
    def __init__(self, publisher_token: str, subscriber_token: str) -> None:
        self.publisher_token = publisher_token
        self.subscriber_token = subscriber_token
        self.publisher: ServerConnection | None = None
        self.subscribers: set[Subscriber] = set()
        self.latest: str | None = None
        self._lock = asyncio.Lock()

    async def authenticate(self, connection: ServerConnection) -> str:
        try:
            raw = await asyncio.wait_for(connection.recv(), AUTH_TIMEOUT_SECONDS)
            request = decode_json(raw)
        except (asyncio.TimeoutError, ProtocolError, ConnectionClosed) as exc:
            raise ProtocolError("authentication required") from exc
        if request.get("type") != "auth" or request.get("role") not in {
            "publisher",
            "subscriber",
        }:
            raise ProtocolError("invalid authentication request")
        role = request["role"]
        supplied = request.get("token")
        expected = self.publisher_token if role == "publisher" else self.subscriber_token
        if not isinstance(supplied, str) or not secrets.compare_digest(supplied, expected):
            raise ProtocolError("authentication failed")
        return role

    async def handler(self, connection: ServerConnection) -> None:
        try:
            role = await self.authenticate(connection)
            if role == "publisher":
                await self.handle_publisher(connection)
            else:
                await self.handle_subscriber(connection)
        except ProtocolError as exc:
            await connection.close(code=1008, reason=str(exc))
        except ConnectionClosed:
            pass

    async def handle_publisher(self, connection: ServerConnection) -> None:
        async with self._lock:
            if self.publisher is not None:
                raise ProtocolError("publisher already connected")
            self.publisher = connection
        LOGGER.info("visualization publisher connected")
        await connection.send('{"type":"auth_ok","role":"publisher"}')
        try:
            async for raw in connection:
                try:
                    message = validate_telemetry(raw)
                except (ProtocolError, ValueError) as exc:
                    await connection.send(
                        json.dumps({"type": "error", "reason": str(exc)}, separators=(",", ":"))
                    )
                    continue
                self.latest = message
                for subscriber in tuple(self.subscribers):
                    subscriber.replace_latest(message)
        finally:
            async with self._lock:
                if self.publisher is connection:
                    self.publisher = None
            LOGGER.info("visualization publisher disconnected")

    async def handle_subscriber(self, connection: ServerConnection) -> None:
        subscriber = Subscriber(connection)
        self.subscribers.add(subscriber)
        LOGGER.info("visualization subscriber connected; count=%d", len(self.subscribers))
        await connection.send('{"type":"auth_ok","role":"subscriber"}')
        if self.latest is not None:
            subscriber.replace_latest(self.latest)
        try:
            while True:
                message_ready = asyncio.create_task(subscriber.queue.get())
                connection_closed = asyncio.create_task(connection.wait_closed())
                done, pending = await asyncio.wait(
                    {message_ready, connection_closed},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                if connection_closed in done:
                    break
                message = message_ready.result()
                await asyncio.wait_for(
                    connection.send(message), SUBSCRIBER_SEND_TIMEOUT_SECONDS
                )
        except asyncio.TimeoutError:
            await connection.close(code=1013, reason="subscriber too slow")
        finally:
            self.subscribers.discard(subscriber)
            LOGGER.info("visualization subscriber disconnected; count=%d", len(self.subscribers))


def require_secret(name: str) -> str:
    value = os.environ.get(name, "")
    if len(value) < 32:
        raise RuntimeError(f"{name} must contain at least 32 characters")
    return value


def tls_context_from_environment() -> ssl.SSLContext | None:
    certificate = os.environ.get("TELEMETRY_TLS_CERT")
    private_key = os.environ.get("TELEMETRY_TLS_KEY")
    if bool(certificate) != bool(private_key):
        raise RuntimeError("TELEMETRY_TLS_CERT and TELEMETRY_TLS_KEY must be set together")
    if not certificate:
        return None
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, private_key)
    return context


async def run() -> None:
    host = os.environ.get("TELEMETRY_HOST", "127.0.0.1")
    port = int(os.environ.get("TELEMETRY_PORT", "8767"))
    hub = TelemetryHub(
        require_secret("TELEMETRY_PUBLISHER_TOKEN"),
        require_secret("TELEMETRY_SUBSCRIBER_TOKEN"),
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop.set)
    ssl_context = tls_context_from_environment()
    scheme = "wss" if ssl_context else "ws"
    async with serve(
        hub.handler,
        host,
        port,
        ssl=ssl_context,
        max_size=MAX_MESSAGE_BYTES,
        compression=None,
        ping_interval=20,
        ping_timeout=20,
    ):
        LOGGER.info("visualization telemetry listening on %s://%s:%d", scheme, host, port)
        await stop.wait()


def main() -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
