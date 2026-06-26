# modules/sys_monitor.py
import time
import platform
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor
import psutil
import GPUtil
import subprocess
import sys

if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
    
    _original_Popen = subprocess.Popen

    class PatchedPopen(_original_Popen):
        def __init__(self, args, **kwargs):
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = CREATE_NO_WINDOW
            super().__init__(args, **kwargs)

    subprocess.Popen = PatchedPopen
    try:
        import GPUtil.GPUtil as gpumod
        gpumod.Popen = PatchedPopen
    except Exception:
        pass
    if hasattr(GPUtil, "Popen"):
        GPUtil.Popen = PatchedPopen

def hex_to_rgb(hex_str: str) -> RGBColor:
    hex_str = hex_str.lstrip('#')
    return RGBColor(
        int(hex_str[0:2], 16),
        int(hex_str[2:4], 16),
        int(hex_str[4:6], 16)
    )

def interpolate_color(c1: RGBColor, c2: RGBColor, ratio: float) -> RGBColor:
    ratio = max(0.0, min(1.0, ratio))
    r = int(c1.red + (c2.red - c1.red) * ratio)
    g = int(c1.green + (c2.green - c1.green) * ratio)
    b = int(c1.blue + (c2.blue - c1.blue) * ratio)
    return RGBColor(r, g, b)

STANDARD_THRESHOLDS = [0.0, 0.25, 0.5, 0.75, 1.0]
STANDARD_COLORS = [
    RGBColor(0, 255, 0),
    RGBColor(127, 255, 0),
    RGBColor(255, 255, 0),
    RGBColor(255, 127, 0),
    RGBColor(255, 0, 0)
]

def get_mapped_color(ratio: float, config: dict) -> RGBColor:
    if config.get("is_custom_color"):
        c_min = hex_to_rgb(config.get("min_color", "#00FF00"))
        c_max = hex_to_rgb(config.get("max_color", "#FF0000"))
        return interpolate_color(c_min, c_max, ratio)
    else:
        if ratio <= 0.0: return STANDARD_COLORS[0]
        if ratio >= 1.0: return STANDARD_COLORS[-1]
        for i in range(len(STANDARD_THRESHOLDS) - 1):
            if STANDARD_THRESHOLDS[i] <= ratio <= STANDARD_THRESHOLDS[i+1]:
                t = (ratio - STANDARD_THRESHOLDS[i]) / (STANDARD_THRESHOLDS[i+1] - STANDARD_THRESHOLDS[i])
                return interpolate_color(STANDARD_COLORS[i], STANDARD_COLORS[i+1], t)

def fetch_metric_value(metric_type: str) -> float:
    try:
        if metric_type == "cpu_usage":
            return psutil.cpu_percent(interval=None)
            
        elif metric_type == "mem_usage":
            return psutil.virtual_memory().percent
            
        elif metric_type == "gpu_usage":
            gpus = GPUtil.getGPUs()
            return gpus[0].load * 100 if gpus else 0.0
            
        elif metric_type == "gpu_temp":
            gpus = GPUtil.getGPUs()
            return gpus[0].temperature if gpus else 0.0
            
        elif metric_type == "cpu_temp":
            if platform.system() != "Windows":
                temps = psutil.sensors_temperatures()
                for entries in temps.values():
                    for entry in entries:
                        if 'core' in entry.label.lower() or 'package' in entry.label.lower():
                            return entry.current
            return psutil.cpu_percent(interval=None) 

        elif metric_type == "battery":
            if hasattr(psutil, "sensors_battery"):
                battery = psutil.sensors_battery()
                if battery is not None:
                    return float(battery.percent)
            return 100.0

    except Exception:
        return 0.0
    return 0.0

def run_system_monitor(config: dict) -> None:
    try:
        client = OpenRGBClient()
    except Exception as e:
        print(f"❌ Failed to connect to OpenRGB: {e}")
        return

    devices = client.devices
    if not devices:
        print("❌ No RGB devices detected.")
        return

    metric = config.get("metric", "cpu_usage")
    min_val = float(config.get("min_val", 0))
    max_val = float(config.get("max_val", 100))
    interval = float(config.get("interval", 1.0))
    scale = float(config.get("brightness", 100)) / 100.0
    
    enable_alert = config.get("enable_alert", False)
    alert_threshold = config.get("alert_threshold", 0.84)

    print(f"📊 System Monitor active on [{metric}]... (Interval: {interval}s)")

    if max_val <= min_val: 
        max_val = min_val + 1.0

    while True:
            current_value = fetch_metric_value(metric)
            
            ratio = (current_value - min_val) / (max_val - min_val)
            ratio = max(0.0, min(1.0, ratio))

            is_critical = False
            if enable_alert:
                if metric == "battery":
                    if ratio <= alert_threshold:
                        is_critical = True
                        print(f"⚠️ CRITICAL STATE: Battery level ({current_value:.1f}%) dropped below alert threshold ({alert_threshold*100:.1f}%)! Blinking...")
                else:
                    if ratio >= alert_threshold:
                        is_critical = True
                        print(f"⚠️ CRITICAL STATE: {metric} ratio ({ratio*100:.1f}%) crossed alert threshold ({alert_threshold*100:.1f}%)! Blinking...")

            if metric == "battery":
                ratio = 1.0 - ratio

            if is_critical:
                base_color = get_mapped_color(ratio, config)
                on_color = RGBColor(int(base_color.red * scale), int(base_color.green * scale), int(base_color.blue * scale))
                off_color = RGBColor(0, 0, 0)
                
                steps = max(1, int(interval / 0.5))
                for s in range(steps):
                    current_blink_color = on_color if (s % 2 == 0) else off_color
                    for device in devices:
                        device.set_color(current_blink_color)
                    time.sleep(0.5)
            else:
                base_color = get_mapped_color(ratio, config)
                final_color = RGBColor(
                    int(base_color.red * scale),
                    int(base_color.green * scale),
                    int(base_color.blue * scale)
                )

                for device in devices:
                    device.set_color(final_color)

                time.sleep(interval)