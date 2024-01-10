from arrapi import RadarrAPI

# from data_manager import DataManager  # Import TMDbManager


class RadarrManager:
    def __init__(self, config_manager, data_manager):
        self.config_manager = config_manager
        self.data_manager = data_manager  # Use TMDbManager instance
        self.radarr = self.initialize_radarr()

    def initialize_radarr(self):
        try:
            radarr_url = self.config_manager.get_config_value("radarr_url")
            radarr_api_key = self.config_manager.get_config_value("radarr_api_key")
            if radarr_url and radarr_api_key:
                return RadarrAPI(radarr_url, radarr_api_key)
        except Exception as e:
            print(f"Error initializing Radarr API: {e}")
            return None

    def add_movie(self, tmdb_id, quality_profile_id, root_folder):
        if self.radarr is None:
            return {"status": "error", "message": "Radarr is not configured."}

        try:
            movie_details = self.data_manager.get_movie_details(
                tmdb_id
            )  # Get movie details using TMDbManager
            movie_title = movie_details.title

            response = self.radarr.add_movie(
                tmdb_id=tmdb_id,
                quality_profile=quality_profile_id,
                root_folder=root_folder,
            )

            if response:
                return {
                    "status": "success",
                    "message": f"*{movie_title}* added to Radarr",
                }
            else:
                return {"status": "error", "message": "Failed to add movie to Radarr"}

        except Exception as e:
            return {"status": "error", "message": str(e)}
