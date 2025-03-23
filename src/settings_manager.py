import json
import os
from dataclasses import dataclass, asdict
from typing import Tuple, Dict

@dataclass
class AppSettings:
    model_color: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    background_color: Tuple[float, float, float] = (0.2, 0.2, 0.2)
    background_gradient: bool = False
    light_states: Dict[str, bool] = None
    light_intensity: float = 1.0
    last_directory: str = None
    show_axes: bool = True
    auto_load_last: bool = False

    def __post_init__(self):
        if self.light_states is None:
            self.light_states = {
                'ambient': True,
                'key': True,
                'fill': True,
                'rim': True
            }
        if self.last_directory is None:
            self.last_directory = os.path.expanduser("~")

class SettingsManager:
    def __init__(self, settings_file="app_settings.json"):
        self.settings_file = os.path.join(
            os.path.expanduser("~"),
            ".stlviewer",
            settings_file
        )
        self.settings = self.load_settings()
    
    def load_settings(self) -> AppSettings:
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    return AppSettings(**data)
        except Exception as e:
            print(f"Error loading settings: {e}")
        return AppSettings()
    
    def save_settings(self):
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(asdict(self.settings), f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def update_settings(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save_settings()
