# modules/cycle.py
import time
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor
from .base import BaseModule, logger

STD_PALETTES = {
    "stdcol3": [RGBColor(255, 0, 0), RGBColor(0, 255, 0), RGBColor(0, 0, 255)],
    "stdcol6": [RGBColor(255, 0, 0), RGBColor(255, 255, 0), RGBColor(0, 255, 0), RGBColor(0, 255, 255), RGBColor(0, 0, 255), RGBColor(255, 0, 255)],
    "stdcol12": [RGBColor(255,0,0), RGBColor(255,127,0), RGBColor(255,255,0), RGBColor(127,255,0), RGBColor(0,255,0), RGBColor(0,255,127), RGBColor(0,255,255), RGBColor(0,127,255), RGBColor(0,0,255), RGBColor(127,0,255), RGBColor(255,0,255), RGBColor(255,0,127)],
    "stdcol24": [RGBColor(255,0,0), RGBColor(255,63,0), RGBColor(255,127,0), RGBColor(255,191,0), RGBColor(255,255,0), RGBColor(191,255,0), RGBColor(127,255,0), RGBColor(63,255,0), RGBColor(0,255,0), RGBColor(0,255,63), RGBColor(0,255,127), RGBColor(0,255,191), RGBColor(0,255,255), RGBColor(0,191,255), RGBColor(0,127,255), RGBColor(0,63,255), RGBColor(0,0,255), RGBColor(63,0,255), RGBColor(127,0,255), RGBColor(191,0,255), RGBColor(255,0,255), RGBColor(255,0,191), RGBColor(255,0,127), RGBColor(255,0,63)]
}

class CycleModule(BaseModule):
    """Animate a sequence of colors across all available devices."""
    def _interpolate_color(self, c1: RGBColor, c2: RGBColor, ratio: float) -> RGBColor:
        """Linear interpolation between two RGBColors."""
        r = int(c1.red + (c2.red - c1.red) * ratio)
        g = int(c1.green + (c2.green - c1.green) * ratio)
        b = int(c1.blue + (c2.blue - c1.blue) * ratio)
        return RGBColor(r, g, b)

    def run(self, colors_arg: list = None, stdcol: str = None, speed: float = 10.0, brightness: float = 100.0):
        """Runs a fluid color cycle animation across all devices."""
        try:
            client = self.client or OpenRGBClient()
        except Exception as e:
            logger.error(f"Failed to connect to OpenRGB Server: {e}")
            return

        if not client.devices:
            logger.warning("No RGB devices detected.")
            return

        colors = []
        if colors_arg:
            try:
                colors = [self.parse_hex_color(c) for c in colors_arg]
            except ValueError as e:
                logger.error(f"Color parsing failed: {e}")
                return
        elif stdcol:
            if stdcol not in STD_PALETTES:
                logger.error(f"Palette '{stdcol}' not found. Defaulting to stdcol6.")
                colors = STD_PALETTES["stdcol6"]
            else:
                colors = STD_PALETTES[stdcol]
        else:
            colors = STD_PALETTES["stdcol6"]

        colors = [self.apply_brightness(c, brightness) for c in colors]
        num_colors = len(colors)
        
        logger.info(f"🌈 Starting fluid color cycle with {num_colors} colors ({speed}s loop time).")
        
        interval = max(0.02, speed / 500) 
        t_start = time.time()

        try:
            while True:
                if self.stop_event and self.stop_event.is_set():
                    logger.info("🛑 Stop signal acknowledged. Safely breaking cycle loop.")
                    break

                t_now = time.time() - t_start
                total_ratio = (t_now % speed) / speed
                
                segment = int(total_ratio * num_colors)
                next_segment = (segment + 1) % num_colors
                segment_ratio = (total_ratio * num_colors) % 1
                
                current_color = self._interpolate_color(colors[segment], colors[next_segment], segment_ratio)

                for device in client.devices:
                    try:
                        device.set_color(current_color)
                    except Exception as e:
                        logger.debug(f"Temporary issue updating {device.name}: {e}")
                        
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Cycle effect stopped manually via CLI execution.")