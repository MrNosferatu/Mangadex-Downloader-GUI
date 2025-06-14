import os
import json

class Settings:
    def __init__(self):
        self.settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
        self.default_settings = {
            "download_dir": os.path.expanduser("~/Downloads"),
            "download_as_pdf": True,
            "preferred_language": "en"
        }
        self.settings = self.load_settings()
    
    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    return json.load(f)
            except:
                return self.default_settings.copy()
        return self.default_settings.copy()
    
    def save_settings(self):
        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f)
    
    def get(self, key, default=None):
        return self.settings.get(key, default)
    
    def set(self, key, value):
        self.settings[key] = value
        self.save_settings()