# TUF RGB Controller

TUF RGB Controller is a desktop application for controlling RGB lighting on keyboards and other devices supported by OpenRGB. It is built with Python and PySide6 and provides several lighting modes that can be controlled from a graphical interface.

## Features

- Control RGB lighting through a GUI
- Support for multiple modes:
  - Turn LEDs off
  - Static Color
  - Color Cycle
  - System Hardware Monitor
  - Reactive & Network Effects
  - Screen & Mouse Sync
  - Time & Focus Controls
  - Spotify Sync Controls
- Show live logs in the app window
- Support for system tray minimization
- Adjustable brightness and custom colors

## Requirements

Before running the project, make sure the following are installed:

- Python 3.9 or newer
- OpenRGB installed and running on your system
- Windows operating system

> This project works only on Windows.

## OpenRGB Setup

Before using this app, install OpenRGB from:

https://openrgb.org

During installation, make sure to select:

- Install System Service

This step is required so the app can communicate with RGB devices properly.

### First Time Setup

For the first time setup, follow these steps:

1. Start **OpenRGB** first
2. Start the **TUF RGB Controller** app
3. Launch any effect (Static Color is recommended)
4. Go to the **SDK Client** panel in OpenRGB and click **Disconnect**
5. You can now close OpenRGB
6. TUF RGB Controller will continue to work without OpenRGB running

## Install Dependencies

From the project folder, run:

```bash
pip install PySide6 openrgb psutil GPUtil pynput pyautogui numpy pillow
```

If you want to use the Spotify mode, install these as well:

```bash
pip install spotipy pycaw
```

## Run the Application

From the project folder, run:

```bash
python rgbgui.py
```

## Project Structure

```text
.
├── rgbgui.py
├── modules/
│   ├── base.py
│   ├── cycle.py
│   ├── off.py
│   ├── reactive.py
│   ├── screen_sync.py
│   ├── spotify.py
│   ├── spotify_sync.py
│   ├── static.py
│   ├── sys_monitor.py
│   └── time_focus.py
└── README.md
```

## Mode Overview

### 1) Turn LEDs off
Turns off the lighting on connected devices.

### 2) Static Color
Applies a fixed color to all supported RGB devices.

### 3) Color Cycle
Animates through a sequence of colors smoothly.

### 4) System Hardware Monitor
Changes the RGB color based on CPU/GPU usage, memory, temperature, or battery status.

### 5) Reactive & Network Effects
- Tracks typing speed and input activity
- Or monitors network ping latency

### 6) Screen & Mouse Sync
Syncs the lighting with the current screen or mouse cursor color.

### 7) Time & Focus Controls
- Matches lighting with the time of day
- Or supports focus timer and break modes

### 8) Spotify Sync Controls
Dynamically changes colors based on Spotify playback.

## Spotify Configuration

To use the Spotify mode, create a file named:

```text
spotify_config.json
```

in the project root with the following content:

```json
{
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET"
}
```

Then use the Setup Spotify API Keys button inside the app to save your credentials.

## Important Notes

- OpenRGB must be installed and running before using this application.
- If your RGB device is not detected by OpenRGB, check your OpenRGB configuration first.
- Some modes may require Administrator privileges, especially keyboard-based reactive features.
- If you want the app icon to appear correctly, make sure app_icon.ico exists in the project root.

## Troubleshooting

If the app does not start:

- Make sure Python is installed correctly
- Make sure all dependencies were installed successfully
- Make sure OpenRGB is running
- Make sure Spotify credentials are valid if you are using the Spotify mode

## Development

If you want to extend the project, the main places to look are:

- [rgbgui.py](rgbgui.py): main GUI and app logic
- [modules/](modules/): implementation of the lighting modes

## License

This project is intended for personal use and further development. If you plan to use it commercially, review the relevant licensing terms before doing so.
