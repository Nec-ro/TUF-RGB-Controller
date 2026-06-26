# modules/off.py
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor
from .base import BaseModule, logger

class OffModule(BaseModule):
    """Switch all LEDs to black to turn them off."""
    def run(self):
        """Turns off all LEDs across all devices."""
        try:
            client = self.client or OpenRGBClient()
            if not client.devices:
                logger.warning("No RGB devices detected to turn off.")
                return

            for device in client.devices:
                device.set_color(RGBColor(0, 0, 0))
            logger.info("💤 All LEDs turned off successfully.")
            
        except Exception as e:
            logger.error(f"Error while turning off LEDs: {e}")