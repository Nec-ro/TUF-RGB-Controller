# modules/static.py
import random
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor
from .base import BaseModule, logger

class StaticModule(BaseModule):
    """Apply a single color to all connected devices."""
    def _generate_vibrant_color(self) -> RGBColor:
        """Generates a random high-brightness color."""
        return RGBColor(
            random.randint(128, 255),
            random.randint(128, 255),
            random.randint(128, 255)
        )

    def run(self, color_arg: str = None, brightness: float = 100.0):
        """Sets a static color on all detected devices."""
        try:
            client = self.client or OpenRGBClient()
        except Exception as e:
            logger.error(f"Failed to connect to OpenRGB Server: {e}")
            return

        if not client.devices:
            logger.warning("No RGB devices detected.")
            return

        if not color_arg or color_arg.upper() == "RANDOM":
            color = self._generate_vibrant_color()
            logger.info(f"🎨 Random color selected: RGB({color.red}, {color.green}, {color.blue})")
        else:
            try:
                color = self.parse_hex_color(color_arg)
            except ValueError as e:
                logger.warning(f"{e} -> Falling back to a vibrant random color.")
                color = self._generate_vibrant_color()

        final_color = self.apply_brightness(color, brightness)
        logger.info(f"✅ Setting static color to all devices: RGB({final_color.red}, {final_color.green}, {final_color.blue}) at {brightness}% brightness")

        for device in client.devices:
            try:
                device.set_color(final_color)
            except Exception as e:
                logger.error(f"Failed to apply color to device '{device.name}': {e}")