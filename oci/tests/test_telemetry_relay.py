import asyncio
import json
import socket
import unittest

from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosedError

from telemetry.telemetry_relay import ProtocolError, TelemetryHub, validate_telemetry


PUBLISHER_TOKEN = "p" * 40
SUBSCRIBER_TOKEN = "s" * 40


def telemetry(sequence: int) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "message_type": "vehicle_visualization",
            "sequence": sequence,
            "gps": {"fix_valid": True},
        }
    )


class ProtocolUnitTests(unittest.TestCase):
    def test_valid_telemetry_is_canonicalized(self):
        parsed = json.loads(validate_telemetry(telemetry(3)))
        self.assertEqual(parsed["sequence"], 3)

    def test_rejects_control_and_invalid_schema(self):
        for raw in (
            '{"schema_version":1,"message_type":"CMD"}',
            '{"schema_version":2,"message_type":"vehicle_visualization"}',
            "[]",
            "not-json",
        ):
            with self.subTest(raw=raw), self.assertRaises(ProtocolError):
                validate_telemetry(raw)


class RelayIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.hub = TelemetryHub(PUBLISHER_TOKEN, SUBSCRIBER_TOKEN)
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        self.port = listener.getsockname()[1]
        listener.close()
        self.server = await serve(
            self.hub.handler,
            "127.0.0.1",
            self.port,
            compression=None,
        )
        self.uri = f"ws://127.0.0.1:{self.port}"

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def authenticate(self, role, token):
        connection = await connect(self.uri, compression=None)
        await connection.send(json.dumps({"type": "auth", "role": role, "token": token}))
        return connection

    async def test_unauthenticated_and_bad_token_rejected(self):
        connection = await connect(self.uri)
        await connection.send("{}")
        with self.assertRaises(ConnectionClosedError):
            await connection.recv()
        bad = await self.authenticate("subscriber", "wrong")
        with self.assertRaises(ConnectionClosedError):
            await bad.recv()

    async def test_publisher_to_subscriber_and_invalid_message_rejection(self):
        publisher = await self.authenticate("publisher", PUBLISHER_TOKEN)
        subscriber = await self.authenticate("subscriber", SUBSCRIBER_TOKEN)
        self.assertEqual(json.loads(await publisher.recv())["type"], "auth_ok")
        self.assertEqual(json.loads(await subscriber.recv())["type"], "auth_ok")
        await publisher.send('{"message_type":"CMD","schema_version":1}')
        self.assertEqual(json.loads(await publisher.recv())["type"], "error")
        await publisher.send(telemetry(9))
        self.assertEqual(json.loads(await asyncio.wait_for(subscriber.recv(), 1))["sequence"], 9)
        await publisher.close()
        await subscriber.close()

    async def test_only_one_publisher(self):
        first = await self.authenticate("publisher", PUBLISHER_TOKEN)
        self.assertEqual(json.loads(await first.recv())["role"], "publisher")
        second = await self.authenticate("publisher", PUBLISHER_TOKEN)
        with self.assertRaises(ConnectionClosedError):
            await second.recv()
        await first.close()

    async def test_latest_state_wins_and_late_subscriber_gets_latest(self):
        publisher = await self.authenticate("publisher", PUBLISHER_TOKEN)
        await publisher.recv()
        await publisher.send(telemetry(1))
        await publisher.send(telemetry(2))
        for _ in range(100):
            if self.hub.latest and json.loads(self.hub.latest)["sequence"] == 2:
                break
            await asyncio.sleep(0.01)
        subscriber = await self.authenticate("subscriber", SUBSCRIBER_TOKEN)
        await subscriber.recv()
        latest = json.loads(await asyncio.wait_for(subscriber.recv(), 1))
        self.assertEqual(latest["sequence"], 2)
        await publisher.close()
        await subscriber.close()


if __name__ == "__main__":
    unittest.main()
