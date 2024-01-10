from tmdbv3api import TMDb, Movie, Person
import requests
import imdb  # pip install imdbpy
import random
import time
import json
import os
import logging
import asyncio
import aiohttp


class DataManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.tmdb = TMDb()
        self.tmdb.api_key = self.config_manager.get_config_value("tmdb_api_key")
        self.movie_api = Movie()
        self.cache_file = "cache.json"  # Path to the JSON cache file
        self.load_cache_from_file()  # Load existing cache

    def load_cache_from_file(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r") as file:
                try:
                    self.cache = json.load(file)
                except json.JSONDecodeError as e:
                    print(f"Error loading cache file: {e}")
                    self.cache = {
                        "movie_details": {},
                        "person_details": {},
                    }  # Initialize with an empty cache if the file is corrupted
        else:
            self.cache = {
                "movie_details": {},
                "person_details": {},
            }  # Initialize with an empty cache if the file does not exist
            self.save_cache_to_file()  # Create a new cache file

    def get_movie_details(self, tmdb_id):
        return self.movie_api.details(tmdb_id)

    def save_cache_to_file(self):
        """Save the current state of the cache to a JSON file with pretty-printing."""
        with open(self.cache_file, "w") as file:
            json.dump(self.cache, file, indent=4, sort_keys=True)

    def get_from_cache(self, key, is_movie=True):
        """Retrieve an item from the cache if it exists."""
        category = "movie_details" if is_movie else "person_details"
        return self.cache[category].get(key)

    def add_to_cache(self, key, data, is_movie=True):
        """Add an item to the cache."""
        category = "movie_details" if is_movie else "person_details"
        self.cache[category][key] = data
        self.save_cache_to_file()  # Save updated cache to file

    def update_tmdb_api_key(self):
        self.tmdb.api_key = self.config_manager.get_config_value("tmdb_api_key")

    def search_movie(self, title):
        return self.movie_api.search(title)

    def get_combined_credits(self, person_id):
        """Fetch combined movie and TV credits for a person."""
        url = f"https://api.themoviedb.org/3/person/{person_id}/combined_credits?api_key={self.tmdb.api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return {}

    def process_combined_credits(self, combined_credits):
        """Format the combined credits data and filter for feature films."""
        feature_film_genre_ids = {
            12,
            14,
            16,
            18,
            27,
            28,
            35,
            36,
            37,
            53,
            80,
            # 99,
            878,
            9648,
            10402,
            10749,
            10751,
            10752,
            # 10770,
        }  # IDs of typical feature film genres
        min_vote_count = 50  # Minimum vote count threshold
        seen_titles = set()  # To track titles and avoid duplicates

        formatted_credits = []

        # Process cast credits
        for credit in combined_credits.get("cast", []):
            if (
                "release_date" in credit
                and "genre_ids" in credit
                and credit.get("vote_count", 0) >= min_vote_count
            ):
                if not feature_film_genre_ids.isdisjoint(set(credit["genre_ids"])):
                    title = self.add_formatted_credit(
                        credit, formatted_credits, seen_titles
                    )

        # Process crew credits, particularly for directing
        for credit in combined_credits.get("crew", []):
            if (
                credit.get("job") == "Director"
                and "release_date" in credit
                and credit.get("vote_count", 0) >= min_vote_count
            ):
                title = self.add_formatted_credit(
                    credit, formatted_credits, seen_titles
                )

        # Sort by release year in descending order
        return sorted(
            formatted_credits,
            key=lambda x: (x["release_year"], -x.get("popularity", 0)),
            reverse=True,
        )

    def add_formatted_credit(self, credit, formatted_credits, seen_titles):
        """Helper function to format and add a credit to the list, avoiding duplicates."""
        title = credit.get("title") if "title" in credit else credit.get("name")
        # Check for duplicates
        if title not in seen_titles:
            date = credit.get("release_date")
            release_year = date.split("-")[0] if date else "N/A"
            credit_info = {
                "title": title,
                "release_year": release_year,
                "popularity": credit.get("popularity"),
                "vote_average": credit.get("vote_average"),
            }
            formatted_credits.append(credit_info)
            seen_titles.add(title)  # Mark this title as seen

    def get_imdb_id(self, title):
        ia = imdb.IMDb()
        search_results = ia.search_movie(title)
        if search_results:
            # Assuming the first search result is the desired one
            return search_results[0].movieID
        return "Not Available"

    def get_imdb_id_for_person(self, name):
        ia = imdb.IMDb()
        search_results = ia.search_person(name)
        if search_results:
            # Assuming the first search result is the desired one
            return search_results[0].personID
        return "Not Available"

    def get_wiki_url(self, title):
        """Retrieve the Wikipedia URL for a given movie title."""
        language_code = "en"  # Language code for English Wikipedia
        search_query = title.replace(" ", "%20")
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={search_query}&format=json"

        try:
            response = requests.get(search_url)
            if response.status_code == 200:
                search_results = response.json()
                if search_results.get("query", {}).get("search"):
                    page_title = search_results["query"]["search"][0]["title"]
                    wiki_url = f"https://{language_code}.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
                    return wiki_url
                else:
                    return "Wikipedia page not found"
            else:
                return "Error in fetching data from Wikipedia"
        except Exception as e:
            return f"Error: {e}"

    def get_movie_card_details(self, tmdb_id):
        cache_key = f"movie_card_{tmdb_id}"
        cached_data = self.get_from_cache(cache_key, is_movie=True)

        if cached_data:
            time.sleep(0.250)  # Add a 350ms delay
            return cached_data

        # Fetch the movie details and credits if not in cache
        movie = self.movie_api.details(tmdb_id)
        credits = self.movie_api.credits(tmdb_id)
        imdb_id = self.get_imdb_id(movie.title)
        director = self.get_crew_member(credits, "Director")
        dop = self.get_crew_member(credits, "Director of Photography")
        writers = self.get_top_writers(credits)  # Get top 5 writers
        stars = self.get_main_actors(credits)  # Get top 5 actors
        wiki_url = self.get_wiki_url(movie.title)

        movie_card_data = {
            "tmdb_id": tmdb_id,
            "title": movie.title,
            "director": director,
            "dop": dop,
            "writers": writers,
            "stars": stars,
            "description": movie.overview,
            "poster_path": f"https://image.tmdb.org/t/p/original{movie.poster_path}"
            if movie.poster_path
            else None,
            "release_date": movie.release_date,
            "vote_average": movie.vote_average,
            "imdb_id": imdb_id,
            "wiki_url": wiki_url,
        }

        # Add the fetched data to the cache
        self.add_to_cache(cache_key, movie_card_data)
        return movie_card_data

    def get_person_details(self, name):
        cache_key = f"person_{name}"
        cached_data = self.get_from_cache(cache_key, is_movie=False)

        if cached_data:
            return cached_data

        person_api = Person()
        search_results = person_api.search(name)

        if search_results:
            person_id = search_results[0].id

            # Fetch the person details
            person_details = person_api.details(person_id)
            imdb_id = self.get_imdb_id_for_person(person_details.name)
            print("HERE IS THE IMDB ID:", imdb_id)

            # Fetch the combined credits for the person using the TMDb API
            combined_credits_url = f"https://api.themoviedb.org/3/person/{person_id}/combined_credits?api_key={self.tmdb.api_key}&language=en-US"
            response = requests.get(combined_credits_url)
            if response.status_code == 200:
                combined_credits = response.json()
                credits_info = self.process_combined_credits(combined_credits)
            else:
                credits_info = []

            # Synchronously get the Wikipedia URL
            wiki_url = self.get_wiki_url(person_details.name)

            # Combine the details and credits to return a single response
            person_data = {
                "name": person_details.name,
                "biography": person_details.biography,
                "birthday": person_details.birthday,
                "deathday": person_details.deathday,
                "place_of_birth": person_details.place_of_birth,
                "profile_path": person_details.profile_path,
                "movie_credits": credits_info,
                "imdb_id": imdb_id,
                "wiki_url": wiki_url,
            }

            # Add the fetched data to the cache
            self.add_to_cache(cache_key, person_data, is_movie=False)
            return person_data

        return {}

    def process_movie_credits(self, movie_credits):
        cast_credits = movie_credits.get("cast", [])

        if not cast_credits:
            return []

        # Convert AsObj to list of dictionaries if needed
        if not isinstance(cast_credits, list):
            cast_credits = [credit.__dict__ for credit in cast_credits]

        # Sort credits by release date in descending order
        sorted_credits = sorted(
            cast_credits,
            key=lambda x: x.get("release_date", "0"),  # Sorting by release_date
            reverse=True,  # Most recent first
        )

        # Format the sorted credits
        formatted_credits = []
        for credit in sorted_credits:
            release_year = (
                credit.get("release_date", "N/A").split("-")[0]
                if credit.get("release_date")
                else "N/A"
            )
            credit_info = {
                "title": credit.get("title", "N/A"),
                "release_year": release_year,
            }
            formatted_credits.append(credit_info)

        return formatted_credits

    def get_crew_member(self, credits, job_title):
        for crew_member in credits["crew"]:
            if crew_member["job"] == job_title:
                return crew_member["name"]
        return "Not Available"

    def get_crew_members(self, credits, job_title):
        return [
            member["name"] for member in credits["crew"] if member["job"] == job_title
        ]

    def get_main_actors(
        self, credits, count=1000
    ):  # Assuming 1000 is a large enough number to include all actors
        actors = [member["name"] for member in credits["cast"]][:count]
        return ", ".join(actors) if actors else "Not Available"

    def get_top_writers(self, credits, count=5):
        writers = [
            member["name"]
            for member in credits["crew"]
            if member["department"] == "Writing"
        ][:count]
        return ", ".join(writers) if writers else "Not Available"
