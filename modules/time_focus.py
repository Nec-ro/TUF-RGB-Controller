# modules/time_focus.py
import time
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor

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

TIME_POINTS = [
    (0.0,  RGBColor(48, 32, 192)),
    (6.0,  RGBColor(255, 165, 0)),
    (12.0, RGBColor(255, 255, 102)),
    (15.0, RGBColor(255, 255, 224)),
    (18.0, RGBColor(255, 158, 169)),
    (22.0, RGBColor(75, 0, 130)),
    (24.0, RGBColor(48, 32, 192))
]

def run_time_focus(config: dict) -> None:
    try:
        client = OpenRGBClient()
    except Exception as e:
        print(f"❌ Failed to connect to OpenRGB: {e}")
        return

    devices = client.devices
    if not devices: return

    sub_mode = config.get("sub_mode", "daylight")
    scale = float(config.get("brightness", 100)) / 100.0

    if sub_mode == "daylight":
        interval = float(config.get("interval", 1.0))
        print("⏰ Time-based daylight lighting running...")
        
        while True:
            lt = time.localtime()
            hour = lt.tm_hour + lt.tm_min / 60.0 + lt.tm_sec / 3600.0
            
            current_color = TIME_POINTS[0][1]
            for i in range(len(TIME_POINTS) - 1):
                if TIME_POINTS[i][0] <= hour < TIME_POINTS[i+1][0]:
                    t = (hour - TIME_POINTS[i][0]) / (TIME_POINTS[i+1][0] - TIME_POINTS[i][0])
                    current_color = interpolate_color(TIME_POINTS[i][1], TIME_POINTS[i+1][1], t)
                    break
            
            final_color = RGBColor(int(current_color.red * scale), int(current_color.green * scale), int(current_color.blue * scale))
            for device in devices:
                device.set_color(final_color)
            time.sleep(interval)

    elif sub_mode == "timer":
        duration_mins = float(config.get("timer_duration", 25))
        gradual = config.get("timer_gradual", True)
        color_x = hex_to_rgb(config.get("color_x", "#00FF00"))
        color_y = hex_to_rgb(config.get("color_y", "#FF0000"))

        total_seconds = duration_mins * 60
        start_time = time.time()
        print(f"⏳ Focus Timer started for {duration_mins} minutes...")

        while True:
            elapsed = time.time() - start_time
            if elapsed >= total_seconds:
                break

            ratio = elapsed / total_seconds
            current_color = interpolate_color(color_x, color_y, ratio) if gradual else color_x

            final_color = RGBColor(int(current_color.red * scale), int(current_color.green * scale), int(current_color.blue * scale))
            for device in devices:
                device.set_color(final_color)
            
            time.sleep(0.5)

        print("🔔 Time's up! Flashing until a key is pressed...")
        flash_color = RGBColor(int(color_y.red * scale), int(color_y.green * scale), int(color_y.blue * scale))
        off_color = RGBColor(0, 0, 0)
        
        key_pressed = False
        def on_any_key_press(key):
            nonlocal key_pressed
            key_pressed = True
            return False

        try:
            from pynput import keyboard
            listener = keyboard.Listener(on_press=on_any_key_press)
            listener.start()
        except ImportError:
            listener = None

        flash_count = 0
        while True:
            for device in devices: device.set_color(flash_color)
            time.sleep(0.3)
            for device in devices: device.set_color(off_color)
            time.sleep(0.3)
            flash_count += 1
            if listener is not None:
                if flash_count >= 10 and key_pressed: break
            else:
                if flash_count >= 10: break

        print("🛑 Alarm dismissed by user.")

        target_reset_color = color_x
        
        if config.get("has_break", True):
            break_duration_mins = float(config.get("break_duration", 5))
            color_z = hex_to_rgb(config.get("color_z", "#00BFFF"))
            break_color = RGBColor(int(color_z.red * scale), int(color_z.green * scale), int(color_z.blue * scale))
            
            print(f"🌊 Break Mode active for {break_duration_mins} minutes...")
            break_seconds = break_duration_mins * 60
            break_start = time.time()
            
            while True:
                if time.time() - break_start >= break_seconds: break
                for device in devices: device.set_color(break_color)
                time.sleep(1.0)
                
            print("🌱 Break is over! Fading smoothly back to focus color...")
            steps = 20
            for step in range(steps + 1):
                fade_ratio = step / steps
                fade_color = interpolate_color(color_z, color_x, fade_ratio)
                final_fade_color = RGBColor(int(fade_color.red * scale), int(fade_color.green * scale), int(fade_color.blue * scale))
                
                for device in devices:
                    device.set_color(final_fade_color)
                time.sleep(0.05)

        reset_color = RGBColor(int(target_reset_color.red * scale), int(target_reset_color.green * scale), int(target_reset_color.blue * scale))
        for device in devices:
            device.set_color(reset_color)
            
        print("🔄 System ready for the next round!")