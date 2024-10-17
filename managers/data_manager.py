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
import sqlite3
import json


class DataManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.tmdb = TMDb()
        self.tmdb.api_key = self.config_manager.get_config_value("tmdb_api_key")
        self.movie_api = Movie()
        self.cache_file = "cache.json"  # Path to the JSON cache file

        # Relative path to movies.db from the current file
        db_path = os.path.join(os.path.dirname(__file__), "database.db")

        # Initialize SQLite connection and cursor
        self.db_conn = sqlite3.connect(db_path)
        self.db_cursor = self.db_conn.cursor()

    logging.basicConfig(
        level=logging.DEBUG,  # You can set this to logging.INFO for less verbosity
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    def get_movie_details(self, tmdb_id):
        logging.debug(f"Fetching movie details for TMDb ID: {tmdb_id}")
        return self.movie_api.details(tmdb_id)

    def save_cache_to_file(self):
        logging.debug(f"Saving cache to {self.cache_file}")
        with open(self.cache_file, "w") as file:
            json.dump(self.cache, file, indent=4, sort_keys=True)
        logging.info("Cache saved successfully.")

    def get_from_cache(self, key, is_movie=True):
        """Retrieve an item from the database if it exists."""
        if is_movie:
            # Fetch movie details from the database
            logging.debug(f"Looking for movie with tmdb_id {key} in the database")
            self.db_cursor.execute("SELECT * FROM movies WHERE tmdb_id = ?", (key,))
            data = self.db_cursor.fetchone()
            if data:
                movie_data = {
                    "tmdb_id": data[0],
                    "title": data[1],
                    "description": data[2],
                    "poster_path": data[3],
                    "release_date": data[4],
                    "vote_average": data[5],
                    "imdb_id": data[6],
                    "wiki_url": data[7],
                }
                logging.debug(f"Cache hit for movie: {key}")
                return movie_data
            else:
                logging.debug(f"Cache miss for movie: {key}")
                return None
        else:
            # Fetch person details from the database
            logging.debug(f"Looking for person with name {key} in the database")
            self.db_cursor.execute("SELECT * FROM people WHERE name = ?", (key,))
            data = self.db_cursor.fetchone()
            if data:
                try:
                    movie_credits = json.loads(data[6]) if data[6] else []
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to decode movie credits JSON: {e}")
                    movie_credits = []

                person_data = {
                    "person_id": data[0],
                    "name": data[1],
                    "biography": data[2],
                    "birthday": data[3],
                    "deathday": data[4],
                    "place_of_birth": data[5],
                    "profile_path": (
                        f"https://image.tmdb.org/t/p/original{data[6]}"
                        if data[6]
                        else None
                    ),
                    "imdb_id": data[7],
                    "wiki_url": data[8],
                    "movie_credits": movie_credits,
                }
                logging.debug(f"Cache hit for person: {key}")
                return person_data
            else:
                logging.debug(f"Cache miss for person: {key}")
                return None

    def add_to_cache(self, movie_data, is_movie=True):
        if is_movie:
            # Insert or replace movie details into the 'movies' table
            self.db_cursor.execute(
                """
                INSERT OR REPLACE INTO movies
                (tmdb_id, title, description, poster_path, release_date, vote_average, imdb_id, wiki_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    movie_data["tmdb_id"],
                    movie_data["title"],
                    movie_data["description"],
                    movie_data["poster_path"],
                    movie_data["release_date"],
                    movie_data["vote_average"],
                    movie_data["imdb_id"],
                    movie_data["wiki_url"],
                ),
            )
            logging.info(f"Added movie to database: {movie_data['title']}")
        else:
            # Insert or replace person details into the 'people' table
            self.db_cursor.execute(
                """
                INSERT OR REPLACE INTO people
                (person_id, name, biography, birthday, deathday, place_of_birth, profile_path, imdb_id, wiki_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    movie_data["person_id"],
                    movie_data["name"],
                    movie_data["biography"],
                    movie_data["birthday"],
                    movie_data["deathday"],
                    movie_data["place_of_birth"],
                    movie_data["profile_path"],
                    movie_data["imdb_id"],
                    movie_data["wiki_url"],
                ),
            )
            logging.info(f"Added person to database: {movie_data['name']}")

        self.db_conn.commit()

    def update_tmdb_api_key(self):
        self.tmdb.api_key = self.config_manager.get_config_value("tmdb_api_key")
        logging.info(f"TMDb API key updated to {self.tmdb.api_key}")

    def search_movie(self, title):
        logging.debug(f"Searching for movie: {title}")
        return self.movie_api.search(title)

    def get_combined_credits(self, person_id):
        """Fetch combined movie and TV credits for a person."""
        # Check if credits already exist in the database for this person
        self.db_cursor.execute(
            "SELECT movie_credits FROM person_details WHERE imdb_id = ?", (person_id,)
        )
        cached_credits = self.db_cursor.fetchone()

        if cached_credits:
            return json.loads(cached_credits[0])

        # If not in database, fetch from the API
        url = f"https://api.themoviedb.org/3/person/{person_id}/combined_credits?api_key={self.tmdb.api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            credits = response.json()

            # Process credits and store them in the database
            self.db_cursor.execute(
                """
                UPDATE person_details
                SET movie_credits = ?
                WHERE imdb_id = ?
            """,
                (json.dumps(credits), person_id),
            )

            self.db_conn.commit()
            return credits
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
            878,
            9648,
            10402,
            10749,
            10751,
            10752,
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
                    self.add_formatted_credit(credit, formatted_credits, seen_titles)

        # Process crew credits, particularly for directing
        for credit in combined_credits.get("crew", []):
            if (
                credit.get("job") == "Director"
                and "release_date" in credit
                and credit.get("vote_count", 0) >= min_vote_count
            ):
                self.add_formatted_credit(credit, formatted_credits, seen_titles)

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
        """Retrieve movie card details from the database or TMDb."""
        logging.debug(f"Fetching movie card details for TMDb ID: {tmdb_id}")

        # Check if movie is already in the database
        cached_data = self.get_from_cache(tmdb_id, is_movie=True)

        if cached_data:
            logging.debug(f"Movie found in database: {cached_data}")

            # Fetch the director, DoP, writers, and stars from the database
            cached_data["director"] = self.get_crew_members(
                cached_data["tmdb_id"], "Director"
            )
            cached_data["dop"] = self.get_crew_members(
                cached_data["tmdb_id"], "Director of Photography"
            )
            cached_data["writers"] = self.get_crew_members(
                cached_data["tmdb_id"], "Writer"
            )
            cached_data["stars"] = self.get_main_actors(cached_data["tmdb_id"])

            logging.debug(f"Returning movie card data: {cached_data}")
            return cached_data

        # If not found in the database, fetch from the API
        logging.debug(
            f"Movie with tmdb_id {tmdb_id} not found in the database, fetching from API."
        )
        try:
            movie = self.movie_api.details(tmdb_id)
            credits = self.movie_api.credits(tmdb_id)
            imdb_id = self.get_imdb_id(movie.title)
            director = self.get_crew_member(credits, "Director")
            dop = self.get_crew_member(credits, "Director of Photography")
            writers = self.get_top_writers(credits)
            stars = self.get_main_actors(credits)
            wiki_url = self.get_wiki_url(movie.title)

            movie_card_data = {
                "tmdb_id": tmdb_id,
                "title": movie.title,
                "director": director,
                "dop": dop,
                "writers": writers,
                "stars": stars,
                "description": movie.overview,
                "poster_path": (
                    f"https://image.tmdb.org/t/p/original{movie.poster_path}"
                    if movie.poster_path
                    else None
                ),
                "release_date": movie.release_date,
                "vote_average": movie.vote_average,
                "imdb_id": imdb_id,
                "wiki_url": wiki_url,
            }

            # Log the data fetched from the API
            logging.debug(f"Fetched movie data from API: {movie_card_data}")

            # Store movie details in the database
            self.add_to_cache(tmdb_id, movie_card_data, is_movie=True)

            return movie_card_data
        except Exception as e:
            logging.error(f"Error fetching movie details for TMDb ID {tmdb_id}: {e}")
            return {}

    def get_person_details(self, name):
        """Retrieve person details from the database or TMDb."""
        cached_data = self.get_from_cache(name, is_movie=False)

        if cached_data:
            logging.debug(f"Returning person details: {cached_data}")
            return cached_data

        # Fetch from API if not found in database
        person_api = Person()
        search_results = person_api.search(name)
        if search_results:
            person_id = search_results[0].id
            person_details = person_api.details(person_id)
            imdb_id = self.get_imdb_id_for_person(person_details.name)
            combined_credits_url = (
                f"https://api.themoviedb.org/3/person/{person_id}/combined_credits"
                f"?api_key={self.tmdb.api_key}&language=en-US"
            )
            response = requests.get(combined_credits_url)
            credits_info = (
                self.process_combined_credits(response.json())
                if response.status_code == 200
                else []
            )

            person_data = {
                "person_id": person_id,
                "name": person_details.name,
                "biography": person_details.biography or "Biography not available",
                "birthday": person_details.birthday or "Unknown",
                "deathday": person_details.deathday or "N/A",
                "place_of_birth": person_details.place_of_birth or "Unknown",
                "profile_path": (
                    f"https://image.tmdb.org/t/p/original{person_details.profile_path}"
                    if person_details.profile_path
                    else None
                ),
                "imdb_id": imdb_id,
                "wiki_url": self.get_wiki_url(person_details.name),
                "movie_credits": credits_info,
            }

            self.add_to_cache(person_data, is_movie=False)
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

    def get_crew_members(self, movie_id, job_title):
        # Fetch crew members with the specified job title from the 'movie_crew' table
        self.db_cursor.execute(
            """
            SELECT p.name 
            FROM movie_crew mc
            JOIN people p ON mc.person_id = p.person_id
            WHERE mc.movie_id = ? AND mc.job = ?
            """,
            (movie_id, job_title),
        )
        crew_members = [row[0] for row in self.db_cursor.fetchall()]
        return ", ".join(crew_members) if crew_members else "Not Available"

    def get_main_actors(self, movie_id, count=15):
        # Fetch main actors from the 'movie_cast' table
        self.db_cursor.execute(
            """
            SELECT p.name
            FROM movie_cast mc
            JOIN people p ON mc.person_id = p.person_id
            WHERE mc.movie_id = ? AND mc.role = 'Actor'
            LIMIT ?
            """,
            (movie_id, count),
        )
        actors = [row[0] for row in self.db_cursor.fetchall()]
        return ", ".join(actors) if actors else "Not Available"

    def get_top_writers(self, credits, count=5):
        writers = [
            member["name"]
            for member in credits["crew"]
            if member["department"] == "Writing"
        ][:count]
        return ", ".join(writers) if writers else "Not Available"
