import json
import os
import logging
import time

# from managers.data_manager import DataManager
import requests
import imdb
from tmdbv3api import TMDb, Movie, Person
import aiohttp
from aiohttp import ClientTimeout
import asyncio
from data_manager import DataManager  # if in a 'managers' folder
from config_manager import ConfigManager
import sqlite3


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class MovieDataBuilder:

    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.tmdb = TMDb()  # Initialize the 'tmdb' attribute
        self.semaphore = asyncio.Semaphore(3)
        self.session = None

        # SQLite setup
        self.db_conn = sqlite3.connect(
            "database.db"
        )  # Connection to the SQLite database
        self.db_cursor = self.db_conn.cursor()
        self.create_tables()

    def create_tables(self):
        logging.info("Called create_tables() to set up database schema.")

        """Create tables if they don't already exist."""
        tables = {
            "movies": """
                CREATE TABLE IF NOT EXISTS movies (
                    tmdb_id INTEGER PRIMARY KEY,
                    title TEXT,
                    description TEXT,
                    poster_path TEXT,
                    release_date TEXT,
                    vote_average REAL,
                    imdb_id TEXT,
                    wiki_url TEXT,
                    directors TEXT,  -- Adding column for directors
                    writers TEXT,    -- Adding column for writers
                    dop TEXT         -- Adding column for Director of Photography (DoP)
                )
            """,
            "people": """
                CREATE TABLE IF NOT EXISTS people (
                    person_id INTEGER PRIMARY KEY,
                    name TEXT,
                    biography TEXT,
                    birthday TEXT,
                    deathday TEXT,
                    place_of_birth TEXT,
                    profile_path TEXT,
                    imdb_id TEXT,
                    wiki_url TEXT
                )
            """,
            "movie_cast": """
                CREATE TABLE IF NOT EXISTS movie_cast (
                    movie_id INTEGER,
                    person_id INTEGER,
                    role TEXT,
                    FOREIGN KEY (movie_id) REFERENCES movies (tmdb_id),
                    FOREIGN KEY (person_id) REFERENCES people (person_id)
                )
            """,
            "movie_crew": """
                CREATE TABLE IF NOT EXISTS movie_crew (
                    movie_id INTEGER,
                    person_id INTEGER,
                    job TEXT,
                    FOREIGN KEY (movie_id) REFERENCES movies (tmdb_id),
                    FOREIGN KEY (person_id) REFERENCES people (person_id)
                )
            """,
            "individual_credits": """
                CREATE TABLE IF NOT EXISTS individual_credits (
                    credit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_id INTEGER,
                    movie_title TEXT,
                    movie_id INTEGER, -- Stores the ID but not full details unless needed
                    role_type TEXT,   -- Could be 'actor', 'writer', 'director', or 'dop'
                    FOREIGN KEY (person_id) REFERENCES people (person_id)
                );
            """,
        }
        for table_name, create_statement in tables.items():
            self.db_cursor.execute(create_statement)
        self.db_conn.commit()

    def is_json_serializable(data):
        try:
            json.dumps(data)
            return True
        except (TypeError, OverflowError):
            return False

    async def search_movie(self, title):
        logging.info(f"search_movie() called with title: {title}")

        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={self.tmdb.api_key}&query={title}"
        data = await self.fetch_api(
            search_url
        )  # Ensure we await the fetch_api call since it is async

        if data and "results" in data:
            return data["results"]
        return []

    def add_credits(self, person_id, combined_credits):
        """
        Store the credits minimally in the `individual_credits` table.
        """
        for credit in combined_credits:
            # Get the movie title and ID
            movie_title = credit.get("title") or credit.get("name")
            movie_id = credit.get("id")
            role_type = credit.get("job") if credit.get("job") else "actor"

            # Check if the credit is already in the database
            self.db_cursor.execute(
                """
                SELECT 1 FROM individual_credits
                WHERE person_id = ? AND movie_title = ? AND role_type = ?
                """,
                (person_id, movie_title, role_type),
            )
            if not self.db_cursor.fetchone():
                # Insert the credit into the `individual_credits` table
                self.db_cursor.execute(
                    """
                    INSERT INTO individual_credits
                    (person_id, movie_title, movie_id, role_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (person_id, movie_title, movie_id, role_type),
                )
                logging.info(f"Added credit: {role_type} in {movie_title}")
        self.db_conn.commit()

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

    @staticmethod
    def is_json_serializable(data):
        try:
            json.dumps(data)
            return True
        except (TypeError, OverflowError):
            return False

    def add_to_cache(self, movie_data, is_movie=True):
        logging.info("add_to_cache() called to add movie/person to database.")

        if is_movie:
            # Insert or replace movie details into the 'movies' table
            self.db_cursor.execute(
                """
                INSERT OR REPLACE INTO movies
                (tmdb_id, title, description, poster_path, release_date, vote_average, imdb_id, wiki_url, directors, writers, dop)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    ", ".join(
                        [
                            director["name"]
                            for director in movie_data.get("director", [])
                        ]
                    ),
                    ", ".join(
                        [writer["name"] for writer in movie_data.get("writers", [])]
                    ),
                    ", ".join([dop["name"] for dop in movie_data.get("dop", [])]),
                ),
            )
            logging.info(f"Added movie to database: {movie_data['title']}")

            # Helper function to ensure person exists in the 'people' table
            def ensure_person_exists(person):
                """Ensure the person exists in the 'people' table, add if not present."""
                if isinstance(person, dict) and "person_id" in person:
                    self.db_cursor.execute(
                        "SELECT 1 FROM people WHERE person_id = ?",
                        (person["person_id"],),
                    )
                    if not self.db_cursor.fetchone():
                        self.db_cursor.execute(
                            """
                            INSERT INTO people (person_id, name, biography, birthday, deathday, place_of_birth, profile_path, imdb_id, wiki_url)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                person["person_id"],
                                person.get("name", ""),
                                person.get("biography", ""),
                                person.get("birthday", ""),
                                person.get("deathday", ""),
                                person.get("place_of_birth", ""),
                                person.get("profile_path", ""),
                                person.get("imdb_id", ""),
                                person.get("wiki_url", ""),
                            ),
                        )
                        logging.info(f"Added person to database: {person['name']}")

            # Insert cast (stars) into the 'movie_cast' table
            for star in movie_data.get("stars", []):
                ensure_person_exists(star)  # Ensure person exists in 'people' table

                # Check if the star already exists in the movie_cast table
                self.db_cursor.execute(
                    """
                    SELECT 1 FROM movie_cast WHERE movie_id = ? AND person_id = ? AND role = ?
                    """,
                    (movie_data["tmdb_id"], star["person_id"], "Actor"),
                )
                exists = self.db_cursor.fetchone()

                if not exists:
                    # Insert the star into the movie_cast table
                    self.db_cursor.execute(
                        """
                        INSERT INTO movie_cast
                        (movie_id, person_id, role)
                        VALUES (?, ?, ?)
                        """,
                        (movie_data["tmdb_id"], star["person_id"], "Actor"),
                    )
                    logging.info(f"Added actor to database: {star['name']}")

            # Insert crew members (directors, DoP, writers) into the 'movie_crew' table
            def insert_crew(crew_list, job):
                normalized_job = job.lower()
                for crew_member in crew_list:
                    ensure_person_exists(crew_member)

                    # Check if the crew member already exists in the movie_crew table
                    self.db_cursor.execute(
                        """
                        SELECT 1 FROM movie_crew WHERE movie_id = ? AND person_id = ? AND job = ?
                        """,
                        (
                            movie_data["tmdb_id"],
                            crew_member["person_id"],
                            normalized_job,
                        ),
                    )
                    exists = self.db_cursor.fetchone()

                    if not exists:
                        # Insert the crew member into the movie_crew table
                        self.db_cursor.execute(
                            """
                            INSERT INTO movie_crew
                            (movie_id, person_id, job)
                            VALUES (?, ?, ?)
                            """,
                            (
                                movie_data["tmdb_id"],
                                crew_member["person_id"],
                                normalized_job,
                            ),
                        )
                        logging.info(
                            f"Added {normalized_job} to database: {crew_member['name']}"
                        )

            # Insert director into the 'movie_crew' table
            insert_crew(movie_data.get("director", []), "Director")

            # Insert DoP into the 'movie_crew' table
            insert_crew(movie_data.get("dop", []), "Director of Photography")

            # Insert writers into the 'movie_crew' table
            insert_crew(movie_data.get("writers", []), "Writer")

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

            # After adding the person, add their credits to `individual_credits`
            if "movie_credits" in movie_data:
                self.add_credits(movie_data["person_id"], movie_data["movie_credits"])

        # Commit changes to the database
        self.db_conn.commit()

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
        }
        min_vote_count = 50
        seen_titles = set()
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

        # Process crew credits for directors, writers, and DoPs
        for credit in combined_credits.get("crew", []):
            if (
                credit.get("job") in ["Director", "Writer", "Director of Photography"]
                and "release_date" in credit
            ):
                if credit.get("vote_count", 0) >= min_vote_count:
                    self.add_formatted_credit(credit, formatted_credits, seen_titles)

        return sorted(
            formatted_credits,
            key=lambda x: (x["release_year"], -x.get("popularity", 0)),
            reverse=True,
        )

    async def get_movie_card_details(self, tmdb_id):
        logging.info(f"get_movie_card_details() called with TMDb ID: {tmdb_id}")

        cached_data = self.get_from_cache(tmdb_id, is_movie=True)

        if cached_data:
            logging.info(f"Movie found in cache: {cached_data['title']}")
            return cached_data

        # If not found in cache, fetch the data from the API using fetch_api
        details_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={self.tmdb.api_key}&language=en-US"
        credits_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/credits?api_key={self.tmdb.api_key}&language=en-US"

        movie = await self.fetch_api(details_url)
        credits = await self.fetch_api(credits_url)

        # Handle case where movie or credits fetch fails
        if not isinstance(movie, dict) or not isinstance(credits, dict):
            logging.error(f"Unexpected response structure for TMDb ID {tmdb_id}")
            return {}

        imdb_id = await self.get_imdb_id(movie.get("title", ""))
        director = self.get_crew_member(credits, "Director")
        dop = self.get_crew_member(credits, "Director of Photography")
        writers = self.get_top_writers(credits)
        stars = self.get_main_actors(credits)
        wiki_url = await self.get_wiki_url(movie.get("title", ""))

        movie_card_data = {
            "tmdb_id": tmdb_id,
            "title": movie.get("title", ""),
            "director": director,
            "dop": dop,
            "writers": writers,
            "stars": stars,
            "description": movie.get("overview", ""),
            "poster_path": (
                f"https://image.tmdb.org/t/p/original{movie.get('poster_path', '')}"
                if movie.get("poster_path")
                else None
            ),
            "release_date": movie.get("release_date", ""),
            "vote_average": movie.get("vote_average", ""),
            "imdb_id": imdb_id,
            "wiki_url": wiki_url,
        }

        logging.info(f"Completed fetching data for movie: {movie_card_data['title']}")

        # Add the fetched data to the cache (SQLite)
        self.add_to_cache(movie_card_data)
        return movie_card_data

    def get_from_cache(self, key, is_movie=True):
        logging.info(
            f"get_from_cache() called with key: {key} and is_movie: {is_movie}"
        )

        if is_movie:
            self.db_cursor.execute("SELECT * FROM movies WHERE tmdb_id = ?", (key,))
            movie = self.db_cursor.fetchone()
            if movie:
                # Fetch cast
                self.db_cursor.execute(
                    "SELECT p.name, mc.role FROM movie_cast mc JOIN people p ON mc.person_id = p.person_id WHERE mc.movie_id = ?",
                    (key,),
                )
                cast = self.db_cursor.fetchall()

                # Fetch crew (writers and director)
                self.db_cursor.execute(
                    "SELECT p.name, mc.job FROM movie_crew mc JOIN people p ON mc.person_id = p.person_id WHERE mc.movie_id = ?",
                    (key,),
                )
                crew = self.db_cursor.fetchall()

                return {
                    "tmdb_id": movie[0],
                    "title": movie[1],
                    "description": movie[2],
                    "poster_path": movie[3],
                    "release_date": movie[4],
                    "vote_average": movie[5],
                    "imdb_id": movie[6],
                    "wiki_url": movie[7],
                    "cast": cast,
                    "crew": crew,
                }
            return None
        else:
            # Fetch person details
            self.db_cursor.execute("SELECT * FROM people WHERE name = ?", (key,))
            person = self.db_cursor.fetchone()
            if person:
                return {
                    "person_id": person[0],
                    "name": person[1],
                    "biography": person[2],
                    "birthday": person[3],
                    "deathday": person[4],
                    "place_of_birth": person[5],
                    "profile_path": person[6],
                    "imdb_id": person[7],
                    "wiki_url": person[8],
                }
            return None

    def get_crew_member(self, credits, job_title):
        members = [
            {"name": member["name"], "person_id": member["id"]}
            for member in credits["crew"]
            if member["job"] == job_title
        ]
        logging.info(f"Filtered {job_title}(s): {members}")
        return members if members else [{"name": "Not Available", "person_id": None}]

    async def fetch_api(self, url, session=None):
        logging.info(f"fetch_api() called with URL: {url}")

        """Fetch data from an API and return the JSON response."""
        session = session or (self.session if self.session else aiohttp.ClientSession())
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                logging.error(f"Failed to fetch from {url}, status: {response.status}")
        except Exception as e:
            logging.error(f"Error fetching from {url}: {e}")
        return None

    async def get_combined_credits(self, person_id):
        search_url = f"https://api.themoviedb.org/3/person/{person_id}/combined_credits?api_key={self.tmdb.api_key}"
        data = await self.fetch_api(search_url)

        if data and "cast" in data:  # Ensure data is valid and contains the 'cast' key
            return data
        return []

    async def get_imdb_id(self, title, max_retries=3, initial_delay=2):
        logging.info(f"get_imdb_id() called with title: {title}")

        if not self.session:
            self.session = aiohttp.ClientSession()

        if not title:
            logging.warning(f"Invalid title provided for IMDb ID lookup: '{title}'")
            return "Not Available"

        ia = imdb.IMDb()
        attempt = 0
        delay = initial_delay

        while attempt < max_retries:
            try:
                search_results = await asyncio.to_thread(ia.search_movie, title)
                if search_results:
                    return search_results[0].movieID
                else:
                    logging.warning(f"No IMDb ID found for movie: '{title}'")
                    return "Not Available"
            except Exception as e:
                attempt += 1
                logging.error(f"Attempt {attempt} failed for '{title}': {e}")
                if attempt < max_retries:
                    logging.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                    delay *= 2  # Increase delay for the next attempt
                else:
                    logging.error(f"All attempts failed for '{title}'")
                    return "Not Available"

    async def get_imdb_id_for_person(self, name, max_retries=3, initial_delay=2):
        if not self.session:
            self.session = aiohttp.ClientSession()

        if not name:
            logging.warning(f"Invalid name provided for IMDb ID lookup: '{name}'")
            return "Not Available"

        ia = imdb.IMDb()
        attempt = 0
        delay = initial_delay

        while attempt < max_retries:
            try:
                search_results = await asyncio.to_thread(ia.search_person, name)
                if search_results:
                    return search_results[0].personID
                else:
                    logging.warning(f"No IMDb ID found for person: '{name}'")
                    return "Not Available"
            except Exception as e:
                attempt += 1
                logging.error(f"Attempt {attempt} failed for '{name}': {e}")
                if attempt < max_retries:
                    logging.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                    delay *= 2  # Increase delay for the next attempt
                else:
                    logging.error(f"All attempts failed for '{name}'")
                    return "Not Available"

    async def get_wiki_url(self, title):
        """
        Retrieve the Wikipedia URL for a given movie title using Wikimedia API.
        """
        language_code = "en"  # Language code for English Wikipedia
        search_query = title.replace(" ", "%20")

        # Wikipedia API endpoint for search
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={search_query}&format=json"

        data = await self.fetch_api(search_url)  # Use the fetch_api helper function
        if data and "query" in data and "search" in data["query"]:
            search_results = data["query"]["search"]
            if search_results:
                page_title = search_results[0]["title"]
                wiki_url = f"https://{language_code}.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
                return wiki_url
        return "Wikipedia page not found"

    async def build_data_for_movie(self, movie_title):
        logging.info(f"build_data_for_movie() called for movie: {movie_title}")

        """Main method to build and save data for a movie and associated people."""
        if not self.session:
            self.session = aiohttp.ClientSession()

        print(f"{movie_title.upper()}: Starting data build for movie")
        try:
            movie_search = await self.search_movie(movie_title)
            if not movie_search:
                print(f"{movie_title.upper()}: No search results for movie.")
                return

            movie_id = movie_search[0]["id"]
            movie_details = await self.get_movie_card_details(movie_id)
            if not movie_details:
                print(f"{movie_title.upper()}: No details found for movie.")
                return

            self.add_to_cache(movie_details, is_movie=True)
            print(f"{movie_title.upper()}: Added movie to database.")

            # Fetch details for all related people
            crew_list = self.get_related_people(movie_details)
            await asyncio.gather(
                *[
                    self.fetch_person_and_movies(name, movie_title.upper())
                    for name in crew_list
                ]
            )

            print(f"{movie_title.upper()}: Finished data build for movie.")
        except Exception as e:
            logging.error(f"{movie_title.upper()}: Failed to fetch details. Error: {e}")
            print(f"{movie_title.upper()}: Error occurred: {e}")

    def get_from_cache_by_title(self, title):
        """
        Check if a movie with the given title exists in the database.
        """
        self.db_cursor.execute("SELECT * FROM movie_details WHERE title = ?", (title,))
        movie = self.db_cursor.fetchone()
        if movie:
            return {
                "tmdb_id": movie[0],
                "title": movie[1],
                "director": movie[2],
                "dop": movie[3],
                "writers": movie[4],
                "stars": movie[5],
                "description": movie[6],
                "poster_path": movie[7],
                "release_date": movie[8],
                "vote_average": movie[9],
                "imdb_id": movie[10],
                "wiki_url": movie[11],
            }
        return None

    logging.info("RUNNNNNIINNNNNGGG FETCH_PERSON_AND_MOVIES()")

    async def fetch_person_and_movies(self, person_name, movie_title):
        logging.info("RUNNNNNIINNNNNGGG FETCH_PERSON_AND_MOVIES()")
        """
        Fetch movies for a given person if they aren't already present in the database.
        """
        # Check if the person is already in the database before fetching
        print(f"{movie_title}: Checking person in database: {person_name}", flush=True)
        person_details = self.get_from_cache(person_name, is_movie=False)

        # Verify if person details are incomplete
        if person_details and all(
            person_details.get(field) for field in ["biography", "birthday", "imdb_id"]
        ):
            print(
                f"{movie_title}: Person already in database: {person_name}", flush=True
            )
            return  # Exit early if the person is already in the database with all details

        # If person is not in the database or has incomplete details, proceed to fetch their details
        print(f"{movie_title}: Fetching details for person: {person_name}", flush=True)
        await self.fetch_and_store_person_details(person_name, movie_title)
        print(
            f"{movie_title}: Fetched and added person to database: {person_name}",
            flush=True,
        )

        # Fetch and store their other movie credits (no recursion)
        star_details = self.get_from_cache(person_name, is_movie=False)
        if star_details:
            movie_fetch_tasks = []  # Collect tasks for fetching each movie
            for credit in star_details.get("movie_credits", []):
                movie_title_credit = credit.get("title")

                # Check if the movie is already in the database by title
                if self.get_from_cache_by_title(movie_title_credit):
                    print(
                        f"{movie_title}: Movie already in database: {movie_title_credit}"
                    )
                    continue  # Skip fetching if already in the database

                print(
                    f"{movie_title}: Fetching movie '{movie_title_credit}' for person: {person_name}",
                    flush=True,
                )
                movie_fetch_tasks.append(
                    self.fetch_and_store_movie_details(movie_title_credit)
                )

            # Limit concurrent movie fetch tasks and avoid overwhelming the API
            semaphore = asyncio.Semaphore(3)  # Adjust the semaphore value as necessary
            async with semaphore:
                await asyncio.gather(*movie_fetch_tasks)

            print(
                f"{movie_title}: Finished fetching movies for person: {person_name}",
                flush=True,
            )

    async def fetch_and_store_person_details(self, person_name, movie_title):
        logging.info(
            f"fetch_and_store_person_details() called for person: {person_name}"
        )

        """
        Fetches details for a person associated with a specific movie title.
        Handles rate limiting and retries if necessary.
        """
        # Ensure the session is initialized
        if not self.session:
            self.session = aiohttp.ClientSession()

        logging.info(f"Fetching person details for {person_name}")

        try:
            # Step 1: Search for the person using the TMDB API
            person_api = Person()
            search_results = person_api.search(person_name)
            if not search_results:
                logging.warning(f"No search results found for person: {person_name}")
                return

            # Step 2: Extract the person ID from the search results
            person_id = search_results[0].id

            # Step 3: Fetch detailed information about the person using the `fetch_api` helper function
            details_url = f"https://api.themoviedb.org/3/person/{person_id}?api_key={self.tmdb.api_key}&language=en-US"
            logging.info(f"Calling API for person: {person_name}")

            # Fetch the details and assign to person_details
            person_details = await self.fetch_api(details_url)

            # Check if person_details is valid
            if not person_details or "id" not in person_details:
                logging.warning(
                    f"No detailed information found for person: {person_name}"
                )
                return

            # Log the response from the API for debugging after the API call
            logging.info(
                f"Fetched person details for {person_name}: ID={person_details.get('id')}, Name={person_details.get('name')}, Birthday={person_details.get('birthday')}"
            )

            # Step 4: Fetch the combined credits for the person
            credits_url = f"https://api.themoviedb.org/3/person/{person_id}/combined_credits?api_key={self.tmdb.api_key}&language=en-US"
            combined_credits = await self.fetch_api(credits_url)

            if not combined_credits or not (
                "cast" in combined_credits or "crew" in combined_credits
            ):
                logging.warning(f"No combined credits found for person: {person_name}")
                return

            # Log a summary of the combined credits for easier debugging
            logging.info(
                f"API response for combined credits ({person_name}): {len(combined_credits.get('cast', []))} cast entries and {len(combined_credits.get('crew', []))} crew entries."
            )

            # Step 5: Process combined credits
            formatted_credits = self.process_combined_credits(combined_credits)

            # Step 6: Prepare data for saving to the database
            person_data = {
                "person_id": person_details.get("id"),
                "name": person_details.get("name", ""),
                "biography": person_details.get("biography", ""),
                "birthday": person_details.get("birthday", ""),
                "deathday": person_details.get("deathday", ""),
                "place_of_birth": person_details.get("place_of_birth", ""),
                "profile_path": person_details.get("profile_path", ""),
                "imdb_id": person_details.get("imdb_id", ""),
                "wiki_url": await self.get_wiki_url(person_details.get("name", "")),
                "movie_credits": formatted_credits,  # Store only the necessary credits information
            }

            logging.info(
                f"Here is the formatted person_data before it goes into the db: {person_data}"
            )

            # Step 7: Add person details to the database
            self.add_to_cache(person_data, is_movie=False)
            logging.info(
                f"{movie_title}: Successfully fetched and added details for person: {person_name}"
            )

        except aiohttp.ClientResponseError as e:
            # Handle rate limiting or HTTP 429 errors specifically
            if e.status == 429 or "rate limit" in str(e).lower():
                logging.warning(
                    f"{movie_title}: Rate limit hit for {person_name}, retrying after delay..."
                )
                await asyncio.sleep(5)  # Wait for 5 seconds before retrying
                await self.fetch_and_store_person_details(
                    person_name, movie_title
                )  # Retry the request
            else:
                logging.error(
                    f"{movie_title}: HTTP error while fetching details for {person_name}: {e}"
                )

        except Exception as e:
            # Handle any other unexpected exceptions
            logging.error(
                f"{movie_title}: Unexpected error while fetching details for {person_name}: {e}"
            )

    def get_main_actors(self, credits, count=15):
        actors = [
            {"name": member["name"], "person_id": member["id"]}
            for member in credits.get("cast", [])
        ][:count]
        return actors if actors else [{"name": "Not Available", "person_id": None}]

    def get_top_writers(self, credits, count=5):
        writers = [
            {"name": member["name"], "person_id": member["id"]}
            for member in credits["crew"]
            if member["department"] == "Writing"
        ][:count]
        return writers if writers else [{"name": "Not Available", "person_id": None}]

    def get_related_people(self, movie_details):
        """Extracts a list of related people (crew and cast) from movie details."""
        related_people = set()  # Use a set to avoid duplicates

        # Get the cast members (e.g., actors)
        if "stars" in movie_details:
            for star in movie_details["stars"]:
                related_people.add(star["name"])

        # Get the directors
        if "director" in movie_details:
            for director in movie_details["director"]:
                related_people.add(director["name"])

        # Get the director of photography (DoP)
        if "dop" in movie_details:
            for dop in movie_details["dop"]:
                related_people.add(dop["name"])

        # Get the writers
        if "writers" in movie_details:
            for writer in movie_details["writers"]:
                related_people.add(writer["name"])

        return list(related_people)


# Usage example with DataManager and ConfigManager instances
# Usage example with DataManager and ConfigManager instances
async def main():
    config_manager = ConfigManager()  # Initialize ConfigManager
    data_manager = DataManager(config_manager)  # Pass ConfigManager to DataManager
    movie_builder = MovieDataBuilder(data_manager)

    # Step 1: Read the list of movie titles from the file
    movie_file = "movies_list.txt"  # File with the list of movies

    try:
        # Initialize aiohttp session
        if not movie_builder.session:
            movie_builder.session = aiohttp.ClientSession()

        with open(movie_file, "r") as file:
            movie_titles = (
                file.read().splitlines()
            )  # Read lines and remove extra whitespace

        # Step 2: Loop through each movie and build data one at a time
        for movie_title in movie_titles:
            await movie_builder.build_data_for_movie(
                movie_title
            )  # Process one movie at a time

    except Exception as e:
        logging.error(f"Error occurred: {e}")
    finally:
        # Ensure the aiohttp session is properly closed
        if movie_builder.session:
            await movie_builder.session.close()
        logging.info("Session closed. Program ended gracefully.")


# Run the async main function
try:
    asyncio.run(main())
except Exception as e:
    logging.error(f"An error occurred during execution: {e}")
