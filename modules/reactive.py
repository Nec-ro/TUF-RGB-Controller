# modules/reactive.py
import time
import subprocess
import platform
import re
from collections import deque
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor

CREATE_NO_WINDOW = 0x08000000

try:
    from pynput import keyboard
except ImportError:
    keyboard = None

def hex_to_rgb(hex_str: str) -> RGBColor:
    hex_str = hex_str.lstrip('#')
    return RGBColor(int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))

def interpolate_color(c1: RGBColor, c2: RGBColor, ratio: float) -> RGBColor:
    ratio = max(0.0, min(1.0, ratio))
    return RGBColor(
        int(c1.red + (c2.red - c1.red) * ratio),
        int(c1.green + (c2.green - c1.green) * ratio),
        int(c1.blue + (c2.blue - c1.blue) * ratio)
    )

STANDARD_THRESHOLDS = [0.0, 0.25, 0.5, 0.75, 1.0]
STANDARD_COLORS = [
    RGBColor(0, 255, 0), RGBColor(127, 255, 0),
    RGBColor(255, 255, 0), RGBColor(255, 127, 0), RGBColor(255, 0, 0)
]

def get_mapped_color(ratio: float, config: dict) -> RGBColor:
    if config.get("is_custom_color"):
        return interpolate_color(hex_to_rgb(config.get("min_color", "#00FF00")), hex_to_rgb(config.get("max_color", "#FF0000")), ratio)
    if ratio <= 0.0: return STANDARD_COLORS[0]
    if ratio >= 1.0: return STANDARD_COLORS[-1]
    for i in range(len(STANDARD_THRESHOLDS) - 1):
        if STANDARD_THRESHOLDS[i] <= ratio <= STANDARD_THRESHOLDS[i+1]:
            t = (ratio - STANDARD_THRESHOLDS[i]) / (STANDARD_THRESHOLDS[i+1] - STANDARD_THRESHOLDS[i])
            return interpolate_color(STANDARD_COLORS[i], STANDARD_COLORS[i+1], t)

def get_ping_latency(host: str) -> float:
    """ارسال یک پینگ تکی و استخراج زمان تاخیر بر اساس سیستم‌عامل"""
    is_win = platform.system() == "Windows"
    cmd = ["ping", "-n" if is_win else "-c", "1", host]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True, timeout=2.0, creationflags=CREATE_NO_WINDOW)
        if is_win:
            match = re.search(r"time[=<](\d+)ms", output)
            if match: return float(match.group(1))
        else:
            match = re.search(r"time=(\d+\.?\d*) ms", output)
            if match: return float(match.group(1))
    except Exception:
        pass
    return -1.0

def run_reactive_mode(config: dict) -> None:
    try:
        client = OpenRGBClient()
    except Exception as e:
        print(f"❌ OpenRGB connection failed: {e}")
        return

    devices = client.devices
    if not devices: return

    mode = config.get("mode", "typespeed")
    min_val = float(config.get("min_val", 0))
    max_val = float(config.get("max_val", 100))
    scale = float(config.get("brightness", 100)) / 100.0
    if max_val <= min_val: max_val = min_val + 1.0

    if mode == "ping":
        host = config.get("host", "google.com")
        interval = float(config.get("interval", 1.0))
        print(f"🌐 Ping Monitor running on [{host}]...")
        
        while True:
            latency = get_ping_latency(host)
            if latency < 0:
                ratio = 1.0
            else:
                ratio = (latency - min_val) / (max_val - min_val)
                ratio = max(0.0, min(1.0, ratio))

            base_color = get_mapped_color(ratio, config)
            final_color = RGBColor(int(base_color.red * scale), int(base_color.green * scale), int(base_color.blue * scale))
            
            for device in devices:
                device.set_color(final_color)
            time.sleep(interval)

    elif mode == "typespeed":
        if not keyboard:
            print("❌ 'pynput' library is missing. Install it via pip.")
            return

        timestamps = deque()

        def on_press(key):
            timestamps.append(time.time())

        try:
            listener = keyboard.Listener(on_press=on_press)
            listener.start()
            print("⌨️ Type Speed Monitor active! Start typing...")
        except Exception as e:
            print(f"❌ Failed to start Keyboard Listener: {e}")
            print("💡 Tip: Try running the application as Administrator.")
            return

        while True:
            now = time.time()
            while timestamps and now - timestamps[0] > 2.0:
                timestamps.popleft()

            cps = len(timestamps) / 2.0

            ratio = (cps - min_val) / (max_val - min_val)
            ratio = max(0.0, min(1.0, ratio))

            base_color = get_mapped_color(ratio, config)
            final_color = RGBColor(int(base_color.red * scale), int(base_color.green * scale), int(base_color.blue * scale))

            for device in devices:
                device.set_color(final_color)

            time.sleep(0.1)