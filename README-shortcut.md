# ODF Message Generator — launch shortcut

Two files:

- `Launch-ODF-Generator.bat` — starts the service and opens the webapp.
- `Install-ODF-Shortcut.bat` — puts a double-click icon on your Desktop (run once).

## Setup

1. Keep both `.bat` files in the project folder, next to each other. They work
   out whichever folder that is, so there is no path to edit and the project
   can be moved or cloned to another machine.
2. Double-click `Install-ODF-Shortcut.bat` once. It creates an **ODF Generator** icon on your Desktop.
3. From now on, double-click that Desktop icon to launch.

## What happens when you launch

1. A console window opens running `uvicorn api.app:app` on `127.0.0.1:8000` (this window shows the server logs — leave it open while you work, close it to stop the service).
2. The launcher waits until the service responds (up to 30 seconds).
3. Your default browser opens `http://127.0.0.1:8000`.

## Notes

- **Virtual environment:** if your project has a `.venv` or `venv` folder, it's activated automatically. If your `uvicorn` lives somewhere else (e.g. a conda env), tell me and I'll adjust the start line.
- **Firewall prompt:** the first launch may show a Windows Defender Firewall prompt for Python/uvicorn — allow it (Private networks is enough for localhost).
- **Port:** the app URL is set at the top of `Launch-ODF-Generator.bat` — edit that line if it ever changes.
- **Browser:** the launcher opens the URL with your default browser rather than naming one. It used to run `start Chrome`, which searched the current directory before `PATH` and did nothing at all if Chrome was not installed. The Desktop icon still borrows the Firefox logo when Firefox is installed, and falls back to the launcher's own icon otherwise — cosmetic either way.
- **The service window:** keep it open while you work. It is the server, and it is also where a generation error prints its traceback — the web page will only tell you the request failed.
