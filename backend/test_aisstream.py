import os
import json
import time
import asyncio
import websockets

from dotenv import load_dotenv


load_dotenv(".env")

API_KEY = os.getenv("AISSTREAM_API_KEY")

if not API_KEY:
    raise RuntimeError("AISSTREAM_API_KEY is missing")

# Mumbai / Arabian Sea test area
BBOX = [
    [
        [18.0, 72.0],
        [20.0, 74.0],
    ]
]

SUBSCRIPTION = {
    "APIKey": API_KEY,
    "BoundingBoxes": BBOX,
}


async def main():

    print("=" * 60)
    print("AISSTREAM DIRECT TEST")
    print("=" * 60)
    print("BBOX:", BBOX)
    print("Connecting...")

    message_count = 0
    position_count = 0

    async with websockets.connect(
        "wss://stream.aisstream.io/v0/stream",
        ping_interval=20,
        ping_timeout=20,
    ) as websocket:

        print("CONNECTED")

        await websocket.send(
            json.dumps(SUBSCRIPTION)
        )

        print("SUBSCRIPTION SENT")
        print("Waiting for AIS messages...")
        print()

        start = time.time()

        while time.time() - start < 30:

            try:

                message = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=5,
                )

                data = json.loads(message)

                message_count += 1

                message_type = data.get(
                    "MessageType"
                )

                print(
                    f"MESSAGE #{message_count}: "
                    f"{message_type}"
                )

                if message_type == "SubscriptionConfirmation":
                    print("SUBSCRIPTION CONFIRMED")

                elif message_type in (
                    "PositionReport",
                    "StandardClassBPositionReport",
                    "ExtendedClassBPositionReport",
                ):

                    position_count += 1

                    print(
                        "POSITION REPORT RECEIVED"
                    )

                    print(
                        json.dumps(
                            data,
                            indent=2
                        )[:1500]
                    )

                    print()

            except asyncio.TimeoutError:

                print(
                    "No message in last 5 seconds..."
                )

        print()
        print("=" * 60)
        print("AIS TEST COMPLETE")
        print("=" * 60)

        print(
            "Total messages:",
            message_count
        )

        print(
            "Position reports:",
            position_count
        )


if __name__ == "__main__":

    asyncio.run(main())