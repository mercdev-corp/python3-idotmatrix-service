# python imports
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, status, Request
from fastapi.exceptions import HTTPException
import asyncio
import os
import signal
import shutil
import uvicorn
from bleak import BleakClient

# idotmatrix imports
from core.idotmatrix.common import Common
from core.idotmatrix.gif import Gif
from core.idotmatrix.image import Image
from core.idotmatrix.const import UUID_WRITE_DATA, UUID_READ_DATA

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

def load_env_file():
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val

load_env_file()

PORT = int(os.getenv("PORT", 9191))

app = FastAPI()

ble = None
currentPixels = 32
currentAdress = ""
ack_event = None

SAFE_WRITE_LEN = 244

def checkBLEconnected():
    if ble is None or not ble.is_connected:
        return False
    return True

last_ack_status = None

async def on_ble_notify(sender, data: bytearray):
    global ack_event, last_ack_status
    hex_str = data.hex()
    status_msg = ""
    if len(data) >= 5:
        last_ack_status = data[4]
        status_map = {
            0: "INVALID / REJECTED (00)",
            1: "NEXT CHUNK (01)",
            2: "NO SPACE (02)",
            3: "DONE / SUCCESS (03)",
        }
        status_msg = f" -> {status_map.get(last_ack_status, f'STATUS {last_ack_status}')}"
    print(f"BLE notification ({len(data)} bytes): {hex_str}{status_msg}")
    if ack_event:
        ack_event.set()

async def bleconnect():
    global ble, ack_event
    ack_event = asyncio.Event()
    ble = BleakClient(currentAdress)
    try:
        await ble.connect()
        print(f"BLE connected to {currentAdress}")
        try:
            await ble.start_notify(UUID_READ_DATA, on_ble_notify)
            print("Subscribed to BLE notifications on UUID_READ_DATA")
            await asyncio.sleep(0.1)
            await send(Common().reset())
            print("Display runtime state reset")
            await asyncio.sleep(0.5)
            await send_default_image()
        except Exception as e:
            print(f"Could not subscribe to BLE notifications: {e}")
    except Exception as e:
        print(f"ble device not found: {e}")

async def bledisconnect():
    global ble, ack_event
    if ble is not None:
        try:
            await ble.stop_notify(UUID_READ_DATA)
        except Exception:
            pass
        await ble.disconnect()
        ble = None
    ack_event = None

async def send(message):
    global ble, ack_event, last_ack_status
    # check if connected
    if not checkBLEconnected():
        print("BLE not connected")
        return False

    async def _send_chunk_data(data: bytes | bytearray):
        for offset in range(0, len(data), SAFE_WRITE_LEN):
            packet = data[offset : offset + SAFE_WRITE_LEN]
            await ble.write_gatt_char(UUID_WRITE_DATA, packet, response=False)
            if offset + SAFE_WRITE_LEN < len(data):
                await asyncio.sleep(0.02)

    try:
        if isinstance(message, list):
            for i, chunk in enumerate(message):
                if ack_event:
                    ack_event.clear()
                last_ack_status = None
                await _send_chunk_data(chunk)
                if ack_event:
                    try:
                        await asyncio.wait_for(ack_event.wait(), timeout=5.0)
                        if last_ack_status == 0:
                            print(f"Chunk {i + 1}/{len(message)} REJECTED by display (status 00), auto-resetting")
                            await ble.write_gatt_char(UUID_WRITE_DATA, Common().reset(), response=False)
                            return False
                        elif last_ack_status == 3:
                            print(f"Upload complete! Device ACK 03 (DONE)")
                        elif last_ack_status == 1:
                            print(f"Chunk {i + 1}/{len(message)} ACK 01 (NEXT)")
                        else:
                            print(f"Chunk {i + 1}/{len(message)} ACK received (status {last_ack_status})")
                    except asyncio.TimeoutError:
                        print(f"Chunk {i + 1}/{len(message)} ACK wait timeout, continuing")
                else:
                    await asyncio.sleep(0.05)
        elif isinstance(message, (bytes, bytearray)):
            if len(message) > SAFE_WRITE_LEN:
                await _send_chunk_data(message)
            else:
                await ble.write_gatt_char(UUID_WRITE_DATA, message, response=False)
        return True
    except Exception as e:
        print(f"Error sending BLE data: {e}")
        return False

async def bleSetBrightness(brightness: int):
    if not checkBLEconnected():
        return
    await send(Common().set_screen_brightness(brightness))

async def bleTurnoff():
    if not checkBLEconnected():
        return
    await send(Common().turn_screen_off())

async def bleTurnon():
    if not checkBLEconnected():
        return
    await send(Common().turn_screen_on())

async def blesendgif(file, process=True):
    global currentPixels
    if not checkBLEconnected():
        print("BLE not connected, cannot send image")
        return

    pixels = currentPixels if currentPixels and currentPixels > 0 else 32

    # Upload file based on extension (GIF vs PNG/image)
    is_gif = file.lower().endswith('.gif')
    if process:
        # Gif processor reliably converts both GIFs and PNGs to 32x32 animation/frame accepted by firmware
        payload = Gif().upload_processed(file_path=file, pixel_size=pixels)
    else:
        if is_gif:
            payload = Gif().upload_unprocessed(file_path=file)
        else:
            payload = Image().upload_unprocessed(file_path=file)

    if payload:
        await send(payload)

async def send_default_image():
    default_image = os.getenv("DEFAULT_IMAGE")
    if not default_image:
        return
    default_image = default_image.strip()
    if not default_image:
        return

    img_path = os.path.join(UPLOAD_DIR, default_image)
    if os.path.isfile(img_path):
        print(f"Applying DEFAULT_IMAGE: {default_image}")
        await blesendgif(img_path, process=True)
    else:
        print(f"DEFAULT_IMAGE file not found: {img_path}")

async def ble_reset_flow():
    await send(Common().reset())
    print("Display runtime state reset")
    await asyncio.sleep(0.5)
    await send_default_image()


@app.get("/BLEconnect/{address}/{pixels}")
async def BLEconnect(address: str, pixels: int, BackgroundTasks: BackgroundTasks):
    global currentAdress, currentPixels
    address = (':'.join(address[i:i+2] for i in range(0,12,2))).upper()
    print(address)
    currentPixels = pixels if pixels > 0 else 32
    if currentAdress != address:
        if checkBLEconnected():
            BackgroundTasks.add_task(bledisconnect)
        currentAdress = address

    if not checkBLEconnected() :
        BackgroundTasks.add_task(bleconnect)
        return "Success"
    return "Already connected"

@app.get("/BLEdisconnect")
async def BLEdisconnect(BackgroundTasks: BackgroundTasks):
    if checkBLEconnected():
        BackgroundTasks.add_task(bledisconnect)
        return "Success"
    return "Not connected"

@app.get("/BLEstatus")
def BLEstatus():
    if not checkBLEconnected():
        return {"connected": False }
    return {"connected": True }

@app.get("/brightness/{brightness}")
async def set_brightness(brightness: int, BackgroundTasks: BackgroundTasks):
    if brightness >= 5 and brightness <= 100:
        BackgroundTasks.add_task(bleSetBrightness, brightness)
        return "Success"
    return "Out of range 5 to 100"

@app.get("/turnoff")
async def turn_off(BackgroundTasks: BackgroundTasks):
    BackgroundTasks.add_task(bleTurnoff)
    return "Success"

@app.get("/turnon")
async def turn_on(BackgroundTasks: BackgroundTasks):
    BackgroundTasks.add_task(bleTurnon)
    return "Success"

@app.get("/reset")
async def ble_reset(BackgroundTasks: BackgroundTasks):
    if not checkBLEconnected():
        return "Not connected"
    BackgroundTasks.add_task(ble_reset_flow)
    return "Success"

@app.get("/getFileNames")
def get_file_names():
    mylist = os.listdir(UPLOAD_DIR)
    return {"count": len(mylist),"filenames": mylist}

@app.get("/shutdown")
async def shutdown_server(BackgroundTasks: BackgroundTasks):
    if checkBLEconnected():
        BackgroundTasks.add_task(bledisconnect)
    os.kill(os.getpid(), signal.SIGTERM)
    return "Shutting down server"

@app.post('/upload')
async def upload_file(request: Request, BackgroundTasks: BackgroundTasks, file: UploadFile = File(...)):
    print(file.filename)
    if file.content_type  != 'image/gif' and file.content_type  != 'image/png':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wow, That's not allowed")
        return

    print("uploaded {} successful".format(file.filename))

    SAVE_F = os.path.join(UPLOAD_DIR, file.filename)

    with open(SAVE_F, 'w+b') as diskfile:
        shutil.copyfileobj(file.file, diskfile)

    print(SAVE_F)

    BackgroundTasks.add_task(blesendgif, SAVE_F)

    return "Success"

@app.get('/uselocal/{filename}')
async def use_local_file(BackgroundTasks: BackgroundTasks, filename: str):
    SAVE_F = os.path.join(UPLOAD_DIR, filename)
    if os.path.isfile(SAVE_F):
        BackgroundTasks.add_task(blesendgif, SAVE_F)
        return "Success"
    else:

        return "File not found"

@app.post('/raw-upload')
async def upload_file(request: Request, BackgroundTasks: BackgroundTasks, file: UploadFile = File(...)):
    print(file.filename)
    if file.content_type  != 'image/gif' and file.content_type  != 'image/png':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wow, That's not allowed")
        return

    print("uploaded {} successful".format(file.filename))

    SAVE_F = os.path.join(UPLOAD_DIR, file.filename)

    with open(SAVE_F, 'w+b') as diskfile:
        shutil.copyfileobj(file.file, diskfile)

    print(SAVE_F)

    BackgroundTasks.add_task(blesendgif, SAVE_F, False)

    return "Success"

@app.get('/raw-uselocal/{filename}')
async def use_local_file(BackgroundTasks: BackgroundTasks, filename: str):
    SAVE_F = os.path.join(UPLOAD_DIR, filename)
    if os.path.isfile(SAVE_F):
        BackgroundTasks.add_task(blesendgif, SAVE_F, False)
        return "Success"
    else:

        return "File not found"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
