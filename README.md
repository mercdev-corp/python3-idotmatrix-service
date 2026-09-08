<br/>

## About The Project

Fork based on [derkalle4/python3-idotmatrix-client](https://github.com/derkalle4/python3-idotmatrix-client), streamlined to provide a lightweight REST API service for controlling iDotMatrix Bluetooth LED displays (16x16, 32x32, etc.).

Features & updates:
* **New firmware support**: Fully supports updated iDotMatrix firmware revisions with LittleFS chunking, exact payload length validation, CRC32 verification, and ACK notifications (`00` Rejected, `01` Next chunk, `03` Completed).
* **Cross-platform**: Works on Linux (BlueZ) and Windows (using Bleak with safe GATT packet slicing to conform with BLE MTU limits).
* **Automatic GIF/PNG adaptation**: GIF and PNG uploads are automatically resized and converted to 32x32 (or configured resolution) with palette optimization to ensure reliable playback.
* **Default image on start/reset**: Automatically uploads and displays your chosen image/animation upon connection or reset.

## Configuration (`.env`)

Copy `.env.example` to `.env` and configure your parameters:

```bash
cp .env.example .env   # On Windows PowerShell: Copy-Item .env.example .env
```

| Variable | Description | Default / Example |
|---|---|---|
| `CWD` | Working directory (used by `idotmatrix.sh`) | `./` |
| `HOST` | Host address for API / scripts | `127.0.0.1` |
| `PORT` | Web server listening port | `9191` |
| `ADDRESS` | Bluetooth MAC address without colons (case-insensitive) | `123456789abc` |
| `PIXELS` | Matrix display resolution (width/height in pixels) | `32` (or `16`) |
| `DEFAULT_IMAGE` | Name of the file in `uploads/` to show automatically on connect/reset | `default_image.gif` |
| `DEFAULT_TURN_OFF` | Turn screen LEDs off after startup procedure completes | `false` (or `true`) |

`.env` is automatically loaded by `app.py` on startup if present.

## How to Run

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Find Bluetooth MAC Address**:
   * **Linux**: `sudo hcitool -i hci0 lescan` or `bluetoothctl scan on`
   * **Windows**: Check Bluetooth settings or use a BLE scanner (look for names starting with `IDM-`).

3. **Configure `.env`**:
   Set `ADDRESS`, `PIXELS`, and optionally `DEFAULT_IMAGE` or `DEFAULT_TURN_OFF` in `.env`.

4. **Start the service**:
   * Directly with Python:
     ```bash
     python app.py
     ```
   * Or using the startup script:
     ```bash
     ./idotmatrix.sh
     ```

5. **Interactive API documentation (Swagger)**:
   Open `http://localhost:9191/docs` in your browser.

## API Endpoints

### Connection & Device Management
* `GET /BLEconnect/{address}/{pixels}` — Connects to the display. E.g. `/BLEconnect/d2317868b878/32`. Upon connection, sends a soft reset, automatically displays `DEFAULT_IMAGE` if configured, and turns off screen if `DEFAULT_TURN_OFF` is enabled.
* `GET /BLEdisconnect` — Disconnects from the display.
* `GET /BLEstatus` — Returns connection status `{"connected": true/false}`.
* `GET /reset` — Sends a runtime soft reset (`04 00 03 80`) to clear device graphics buffers and re-applies `DEFAULT_IMAGE`.
* `GET /shutdown` — Safely disconnects BLE and terminates the server process.

### Display Controls
* `GET /turnon` — Turns screen LEDs on.
* `GET /turnoff` — Turns screen LEDs off (keeps BLE connected).
* `GET /brightness/{brightness}` — Sets brightness from 5 to 100 (%).

### Media & Animations
* `POST /upload` — Uploads `.gif` or `.png` (multipart/form-data). The file is saved in `uploads/`, resized/palettized to the display resolution, and immediately shown.
* `GET /uselocal/{filename}` — Loads an existing file from `uploads/`, processes it for display resolution, and shows it.
* `POST /raw-upload` — Uploads and sends image data without resizing or processing checks.
* `GET /raw-uselocal/{filename}` — Displays a local file without processing checks.
* `GET /getFileNames` — Returns list and count of all available media files in `uploads/`.

### Home Assistant Integration
Examples for Home Assistant are provided in `homeassistant/configuration.yaml` and `homeassistant/automations.yaml` (update host, port, MAC address, and pixel count).

## Goals
- [x] build a webserver accepting rest commands 
- [x] accept png/gif data which is then sent to the display
- [x] accept on off commands 
- [x] accept brightness commands
- [x] accept shutdown command
- [x] save files and set via filename
- [x] retrieve local file list
- [x] homeassistant example configuration.yaml and automations.yaml
- [x] support updated firmware protocol with CRC32 and chunked ACK handling
- [x] support default image on start and soft reset
- [ ] option to save files processed

## Built With

* [Python 3](https://www.python.org/downloads/)
* [asyncio](https://docs.python.org/3/library/asyncio.html)
* [bleak](https://github.com/hbldh/bleak)
* [pillow](https://python-pillow.org)
* [fastapi](https://fastapi.tiangolo.com/)
* [uvicorn](https://www.uvicorn.org/)

## TODOs

Strip project form everything unneeded

Move everything into a docker

## Notes 

If you really need other functions via REST, feel free to implement them yourself, the "old" code is still in the project and it can easily be integrated. Or if you really struggle you can open a issue and I will implement it. (I wont do any further reverse engineering)

## License

Distributed under the GNU GENERAL PUBLIC License. See [LICENSE](https://github.com/derkalle4/python3-idotmatrix-client/blob/main/LICENSE) for more information.

## Authors

* [Christoph Butzhammer](https://github.com/butz6617)

## Acknowledgements

* [Kalle Minkner](https://github.com/derkalle4) - *Project Founder of forked project*
* [Jon-Mailes Graeffe](https://github.com/jmgraeffe) - *Co-Founder of forked project*
* [Othneil Drew](https://github.com/othneildrew/Best-README-Template) - *README Template*
* [LordRippon](https://github.com/LordRippon) - *Reverse Engineering for the Displays*
* [8none1](https://github.com/8none1) - *Reverse Engineering for the Displays*
* [schorsch3000](https://github.com/schorsch3000) - *smaller fixes*
* [tekka007](https://github.com/tekka007) - *code refactoring and reverse engineering*
* [inselberg](https://github.com/inselberg) - *Reverse Engineering for the Displays*
