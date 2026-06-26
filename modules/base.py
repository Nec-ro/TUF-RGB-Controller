# modules/base.py
import logging
import re
from openrgb.utils import RGBColor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("RGB_Controller")

class BaseModule:
    """Common base class for RGB modules that talk to OpenRGB."""
    def __init__(self, client=None, stop_event=None):
        """
        Base class for all RGB modules.
        
        Args:
            client: Shared OpenRGBClient instance (optional).
            stop_event: threading.Event to safely interrupt infinite loops from the GUI.
        """
        self.client = client
        self.stop_event = stop_event

    def apply_brightness(self, color: RGBColor, brightness: float) -> RGBColor:
        """Scales the brightness of a given RGBColor (0-100)."""
        scale = max(0.0, min(100.0, brightness)) / 100.0
        return RGBColor(
            int(color.red * scale),
            int(color.green * scale),
            int(color.blue * scale)
        )

    @staticmethod
    def parse_hex_color(value: str) -> RGBColor:
        """Converts a HEX color string to an OpenRGB RGBColor object."""
        match = re.fullmatch(r'#?([A-Fa-f0-9]{6})', value)
        if not match:
            raise ValueError(f"Invalid HEX color format: '{value}'. Use standard formats like #FF00AA or FF00AA")
        hex_val = match.group(1)
        return RGBColor(
            int(hex_val[0:2], 16),
            int(hex_val[2:4], 16),
            int(hex_val[4:6], 16)
        )