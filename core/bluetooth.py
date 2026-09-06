import asyncio
from bleak import BleakClient
import logging
import time

# idotmatrix imports
from .idotmatrix.const import UUID_READ_DATA, UUID_WRITE_DATA


class Bluetooth:
    address = None
    client = None
    mtu_size = None

    def __init__(self, address):
        self.address = address

    async def response_handler(self, sender, data):
        """Simple response handler which prints the data received."""

    async def connect(self):
        print("trying to connect BLE")
        try:
            # create client
            self.client = BleakClient(self.address)
            # connect client
            await self.client.connect()
            # Initialise Response Message Handler
            #await self.client.start_notify(UUID_READ_DATA, self.response_handler)
        except Exception as e:
            if self.client and self.client.is_connected:
                await self.disconnect()
            return False
        return True

    async def disconnect(self):
        if self.client is not None:
            try:
                await self.client.stop_notify(UUID_READ_DATA)
            except Exception:
                pass
            await self.client.disconnect()

    async def send(self, message):
        # check if connected
        if self.client is None or not self.client.is_connected:
            if not await self.connect():
                return False

        SAFE_WRITE_LEN = 244

        async def _send_chunk_data(data):
            for offset in range(0, len(data), SAFE_WRITE_LEN):
                packet = data[offset : offset + SAFE_WRITE_LEN]
                await self.client.write_gatt_char(UUID_WRITE_DATA, packet, response=False)
                if offset + SAFE_WRITE_LEN < len(data):
                    await asyncio.sleep(0.02)

        try:
            if isinstance(message, list):
                for i, chunk in enumerate(message):
                    await _send_chunk_data(chunk)
                    if i + 1 < len(message):
                        await asyncio.sleep(0.05)
            elif isinstance(message, (bytes, bytearray)):
                if len(message) > SAFE_WRITE_LEN:
                    await _send_chunk_data(message)
                else:
                    await self.client.write_gatt_char(UUID_WRITE_DATA, message, response=False)
            return True
        except Exception as e:
            logging.error(f"Error sending BLE data: {e}")
            return False
