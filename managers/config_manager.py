import yaml
import os


class ConfigManager:
    def __init__(self, config_directory="config", config_filename="config.yaml"):
        self.config_path = os.path.join(config_directory, config_filename)
        self.config = self.load_config()

    def load_config(self):
        # Load configuration from a YAML file, or create a default one
        if not os.path.exists(self.config_path):
            self.create_default_config()
        with open(self.config_path, "r") as file:
            return yaml.safe_load(file)

    def create_default_config(self):
        # Create and save a default configuration file
        default_config = {
            "tmdb_api_key": "",
            "radarr_url": "",
            "radarr_api_key": "",
            "openai_api_key": "",
            "discord_token": "",
            "radarr_quality": "",
            "selected_model": "",
            "max_chars": 65540,  # Default value, can be adjusted
            "discord_channel": "",
            "radarr_root_folder": "",
        }
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w") as file:
            yaml.dump(default_config, file)
        return default_config

    def get_config_value(self, key):
        # Retrieve a specific configuration value
        return self.config.get(key)
