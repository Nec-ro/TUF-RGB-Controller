# modules/spotify_sync.py
import time
import os
import json
import random
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor
from pycaw.pycaw import AudioUtilities

STD_COLORSETS = {
    "stdcol3": [RGBColor(255,0,0), RGBColor(0,255,0), RGBColor(0,0,255)],
    "stdcol6": [RGBColor(255,0,0), RGBColor(255,255,0), RGBColor(0,255,0),
                RGBColor(0,255,255), RGBColor(0,0,255), RGBColor(255,0,255)],
    "stdcol12": [
        RGBColor(255,0,0), RGBColor(255,127,0), RGBColor(255,255,0), RGBColor(127,255,0),
        RGBColor(0,255,0), RGBColor(0,255,127), RGBColor(0,255,255), RGBColor(0,127,255),
        RGBColor(0,0,255), RGBColor(127,0,255), RGBColor(255,0,255), RGBColor(255,0,127)],
    "stdcol24": [
        RGBColor(255,0,0), RGBColor(255,63,0), RGBColor(255,127,0), RGBColor(255,191,0),
        RGBColor(255,255,0), RGBColor(191,255,0), RGBColor(127,255,0), RGBColor(63,255,0),
        RGBColor(0,255,0), RGBColor(0,255,63), RGBColor(0,255,127), RGBColor(0,255,191),
        RGBColor(0,255,255), RGBColor(0,191,255), RGBColor(0,127,255), RGBColor(0,63,255),
        RGBColor(0,0,255), RGBColor(63,0,255), RGBColor(127,0,255), RGBColor(191,0,255),
        RGBColor(255,0,255), RGBColor(255,0,191), RGBColor(255,0,127), RGBColor(255,0,63)
    ]
}

def interpolate_color(c1, c2, ratio):
    ratio = max(0.0, min(1.0, ratio))
    return RGBColor(
        int(c1.red + (c2.red - c1.red) * ratio),
        int(c1.green + (c2.green - c1.green) * ratio),
        int(c1.blue + (c2.blue - c1.blue) * ratio)
    )

def get_volume_ratio(sp):
    try:
        device = AudioUtilities.GetSpeakers()
        system_volume = device.EndpointVolume.GetMasterVolumeLevelScalar()
        playback = sp.current_playback()
        if playback and 'device' in playback:
            spotify_volume = playback['device']['volume_percent'] / 100 
            return max(system_volume * spotify_volume, 0.1)
    except: pass
    return 0.5

def run_spotify_sync(config: dict, error_queue=None) -> None:
    config_file = "spotify_config.json"
    if not os.path.exists(config_file):
        print("❌ Error: Spotify credentials missing.")
        return

    with open(config_file, "r") as f:
        creds = json.load(f)

    client_id = creds.get("client_id")
    client_secret = creds.get("client_secret")
    
    if not client_id or not client_secret:
        print("❌ Error: Invalid Spotify credentials.")
        return

    try:
        sp_oauth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri="http://127.0.0.1:8888/callback",
            scope="user-read-playback-state",
            open_browser=True
        )
        sp = spotipy.Spotify(auth_manager=sp_oauth)
    except Exception as e:
        print(f"❌ Auth Error: {e}")
        return

    try:
        client = OpenRGBClient()
    except: return

    devices = client.devices
    if not devices: return

    palette_name = config.get("palette", "stdcol6")
    no_vol = config.get("no_vol", False)
    scale = float(config.get("brightness", 100)) / 100.0
    colors = STD_COLORSETS.get(palette_name, STD_COLORSETS["stdcol6"])

    track_history = {}
    color_idx = random.randint(0, len(colors) - 1)
    current_track_id = None

    print("🎵 Spotify Link Active...")

    while True:
        try:
            try:
                playback = sp.current_playback()
            except spotipy.exceptions.SpotifyException as spotify_err:
                if spotify_err.http_status == 403:
                    print("\n[SPOTIFY ERROR] HTTP 403: Active premium subscription required.")
                    
                    warning_color = RGBColor(int(64 * scale), 0, 0)
                    for device in devices: device.set_color(warning_color)
                    
                    if error_queue is not None:
                        error_queue.put("PREMIUM_REQUIRED")
                    return
                else:
                    raise spotify_err

            if playback and playback.get('is_playing') and playback.get('item'):
                track_id = playback['item']['id']

                if track_id != current_track_id:
                    current_track_id = track_id
                    if track_id not in track_history:
                        start_color = colors[color_idx % len(colors)]
                        color_idx += 1
                        end_color = colors[color_idx % len(colors)]
                        track_history[track_id] = (start_color, end_color)
                    else:
                        start_color, end_color = track_history[track_id]

                progress = playback['progress_ms']
                duration = playback['item']['duration_ms']
                ratio = progress / duration if duration > 0 else 0
                
                current_color = interpolate_color(start_color, end_color, ratio)
                vol_ratio = 1.0 if no_vol else get_volume_ratio(sp)
                
                final_color = RGBColor(
                    int(current_color.red * vol_ratio * scale),
                    int(current_color.green * vol_ratio * scale),
                    int(current_color.blue * vol_ratio * scale)
                )
                
                for device in devices:
                    device.set_color(final_color)
                time.sleep(0.25)
            else:
                idle_color = RGBColor(int(32 * scale), int(32 * scale), int(32 * scale))
                for device in devices:
                    device.set_color(idle_color)
                time.sleep(1.0)
        except Exception:
            time.sleep(1.0)