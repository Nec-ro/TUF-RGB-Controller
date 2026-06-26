# modules/screen_sync.py
import time
import subprocess
from collections import Counter
import pyautogui
import numpy as np
from PIL import ImageGrab, ImageStat
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor

def get_pixel_under_mouse(x, y):
    try:
        img = ImageGrab.grab(bbox=(x, y, x + 1, y + 1))
        return img.getpixel((0, 0))
    except Exception:
        return 0, 0, 0

def get_dominant_color_precise():
    try:
        img = ImageGrab.grab().convert('RGB')
        img = img.resize((60, 60))
        pixels = list(img.getdata())
        color_count = Counter(pixels)
        return color_count.most_common(1)[0][0]
    except Exception:
        return 0, 0, 0

def get_screen_average():
    try:
        img = ImageGrab.grab()
        stat = ImageStat.Stat(img)
        return [int(c) for c in stat.mean[:3]]
    except Exception:
        return 0, 0, 0

def enhance_color(x: int) -> int:
    offset = x - 128
    cube_root = offset ** (1/3) if offset >= 0 else -((-offset) ** (1/3))
    result = 128 + 25.4 * cube_root
    return max(0, min(255, round(result)))

def apply_color_boosting(r, g, b):
    R, G, B = r, g, b
    if g > r: G += 8
    if g > b: G += 8
    if r > g: R += 8
    if r > b: R += 8
    if b > g: B += 8
    if b > r: B += 8

    return enhance_color(R), enhance_color(G), enhance_color(B)

def run_screen_sync(config: dict) -> None:
    try:
        client = OpenRGBClient()
    except Exception as e:
        print(f"❌ Failed to connect to OpenRGB: {e}")
        return

    devices = client.devices
    if not devices:
        return

    method = config.get("method", "scrn_avg")
    do_enhancing = config.get("do_enhancing", True)
    interval = float(config.get("interval", 0.1))
    scale = float(config.get("brightness", 100)) / 100.0

    print(f"🖥️ Screen Sync Loop Started. Method: [{method}]\n")

    while True:
        if method == "mouse":
            x, y = pyautogui.position()
            r, g, b = get_pixel_under_mouse(x, y)
        elif method == "scrn_dom":
            r, g, b = get_dominant_color_precise()
        else:
            r, g, b = get_screen_average()

        if do_enhancing:
            r, g, b = apply_color_boosting(r, g, b)

        final_color = RGBColor(
            int(r * scale),
            int(g * scale),
            int(b * scale)
        )

        for device in devices:
            device.set_color(final_color)

        time.sleep(interval)