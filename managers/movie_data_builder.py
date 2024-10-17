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
        """Create tables if they don't already exist."""

        # Create a table for movie details
        self.db_cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS movies (
                tmdb_id INTEGER PRIMARY KEY,
                title TEXT,
                description TEXT,
                poster_path TEXT,
                release_date TEXT,
                vote_average REAL,
                imdb_id TEXT,
                wiki_url TEXT
            )
        """
        )

        # Create a table for person details
        self.db_cursor.execute(
            """
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
        """
        )

        # Create a table for movie cast
        self.db_cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS movie_cast (
                movie_id INTEGER,
                person_id INTEGER,
                role TEXT,
                FOREIGN KEY (movie_id) REFERENCES movies (tmdb_id),
                FOREIGN KEY (person_id) REFERENCES people (person_id)
            )
        """
        )

        # Create a table for movie crew
        self.db_cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS movie_crew (
                movie_id INTEGER,
                person_id INTEGER,
                job TEXT,  -- 'Director', 'Writer', 'DOP'
                FOREIGN KEY (movie_id) REFERENCES movies (tmdb_id),
                FOREIGN KEY (person_id) REFERENCES people (person_id)
            )
        """
        )

        self.db_conn.commit()

    def is_json_serializable(data):
        try:
            json.dumps(data)
            return True
        except (TypeError, OverflowError):
            return False

    async def search_movie(self, title):
        if not self.session:
            self.session = aiohttp.ClientSession()

        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={self.tmdb.api_key}&query={title}"
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url) as response:
                if response.status == 200:
                    # print("Here is the response from search_movie: ", response)
                    data = await response.text()
                    # print("Here is the data from search_movie: ", data)
                    return json.loads(data)["results"]
                else:
                    return []

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
        if is_movie:
            # Insert movie details into the 'movies' table

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

            # Insert cast (stars) into the 'movie_cast' table
            # Insert cast (stars) into the 'movie_cast' table, using an empty list if 'stars' is missing
            for star in movie_data.get("stars", []):
                if isinstance(star, dict) and "person_id" in star:
                    self.db_cursor.execute(
                        """
                        INSERT OR REPLACE INTO movie_cast
                        (movie_id, person_id, role)
                        VALUES (?, ?, ?)
                        """,
                        (movie_data["tmdb_id"], star["person_id"], "Actor"),
                    )

            # Insert writers into the 'movie_crew' table, using an empty list if 'writers' is missing
            for writer in movie_data.get("writers", []):
                if isinstance(writer, dict) and "person_id" in writer:
                    self.db_cursor.execute(
                        """
                        INSERT OR REPLACE INTO movie_crew
                        (movie_id, person_id, job)
                        VALUES (?, ?, ?)
                        """,
                        (movie_data["tmdb_id"], writer["person_id"], "Writer"),
                    )

            # Insert director into the 'movie_crew' table, using a dictionary with 'Not Available' if 'director' is missing
            director = movie_data.get("director", {})
            if isinstance(director, dict) and "person_id" in director:
                self.db_cursor.execute(
                    """
                    INSERT OR REPLACE INTO movie_crew
                    (movie_id, person_id, job)
                    VALUES (?, ?, ?)
                    """,
                    (movie_data["tmdb_id"], director["person_id"], "Director"),
                )

            # Insert DOP into the 'movie_crew' table, using a dictionary with 'Not Available' if 'dop' is missing
            dop = movie_data.get("dop", {})
            if isinstance(dop, dict) and "person_id" in dop:
                self.db_cursor.execute(
                    """
                    INSERT OR REPLACE INTO movie_crew
                    (movie_id, person_id, job)
                    VALUES (?, ?, ?)
                    """,
                    (
                        movie_data["tmdb_id"],
                        dop["person_id"],
                        "Director of Photography",
                    ),
                )

        else:
            # Insert person details into the 'people' table
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

    async def get_movie_card_details(self, tmdb_id):
        cache_key = f"movie_card_{tmdb_id}"
        cached_data = self.get_from_cache(tmdb_id, is_movie=True)

        if cached_data:
            logging.info(f"Movie found in cache: {cached_data['title']}")
            return cached_data

        # If not found in cache, fetch the data from the API
        async with aiohttp.ClientSession() as session:
            details_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={self.tmdb.api_key}&language=en-US"
            credits_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/credits?api_key={self.tmdb.api_key}&language=en-US"

            try:
                # Fetch the movie details
                async with session.get(details_url) as details_response:
                    if details_response.status == 200:
                        movie = await details_response.json()
                        # logging.info(
                        #    f"Movie data type: {type(movie)}"
                        # )  # Log the type of movie data
                        # logging.info(
                        #    f"Movie data content: {json.dumps(movie, indent=2)}"
                        # )
                        logging.info(
                            f"Fetched details for movie: {movie.get('title', 'N/A')}"
                        )
                    else:
                        logging.error(
                            f"Failed to fetch movie details, status: {details_response.status}"
                        )
                        return {}

                # Fetch the movie credits
                async with session.get(credits_url) as credits_response:
                    if credits_response.status == 200:
                        credits = await credits_response.json()
                        # logging.info(
                        #    f"Credits data type: {type(credits)}"
                        # )  # Log the type of credits data
                        # logging.info(
                        #    f"Credits data content: {json.dumps(credits, indent=2)}"
                        # )
                        logging.info(
                            f"Fetched credits for movie: {movie.get('title', 'N/A')}"
                        )
                    else:
                        logging.error(
                            f"Failed to fetch credits, status: {credits_response.status}"
                        )
                        return {}

            except Exception as e:
                logging.error(f"Error during API call: {e}")
                return {}

        # Validate that movie and credits are dictionaries
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
        for crew_member in credits["crew"]:
            if crew_member["job"] == job_title:
                return crew_member["name"]
        return "Not Available"

    async def get_person_details(self, name):
        """
        Fetches details for a person by name, including biography, movie credits, and IMDb and Wikipedia links.
        Caches the data if not already present in the database.
        """
        # Check for cached data
        cached_data = self.get_from_cache(name, is_movie=False)
        if cached_data:
            logging.info(f"Cache hit for person: {name}")
            return cached_data

        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            # Search for the person using the TMDB API
            person_api = Person()
            search_results = person_api.search(name)
            if not search_results:
                logging.warning(f"No search results found for person: {name}")
                return {}

            # Extract the person ID from the search results
            person_id = search_results[0].id
            async with aiohttp.ClientSession() as session:
                # Fetch detailed information about the person
                details_url = f"https://api.themoviedb.org/3/person/{person_id}?api_key={self.tmdb.api_key}&language=en-US"
                person_details = await self.fetch_async_with_session(
                    session, details_url
                )
                if not person_details:
                    logging.warning(f"No detailed information found for person: {name}")
                    return {}

                # Extract person ID from the details for consistency
                person_id = person_details.get("id")
                if not person_id:
                    logging.error(f"Person ID missing in details for: {name}")
                    return {}

                # Fetch additional information such as IMDb ID and Wikipedia URL
                imdb_id = await self.get_imdb_id_for_person(
                    person_details.get("name", "")
                )
                wiki_url = await self.get_wiki_url(person_details.get("name", ""))

                # Fetch the person's combined credits (movies, TV shows)
                combined_credits_url = f"https://api.themoviedb.org/3/person/{person_id}/combined_credits?api_key={self.tmdb.api_key}&language=en-US"
                combined_credits = await self.fetch_async_with_session(
                    session, combined_credits_url
                )
                credits_info = self.process_combined_credits(combined_credits)

                # Compile all the gathered information into a dictionary
                person_data = {
                    "person_id": person_id,
                    "name": person_details.get("name", ""),
                    "biography": person_details.get("biography", ""),
                    "birthday": person_details.get("birthday", ""),
                    "deathday": person_details.get("deathday", ""),
                    "place_of_birth": person_details.get("place_of_birth", ""),
                    "profile_path": person_details.get("profile_path", ""),
                    "movie_credits": credits_info,
                    "imdb_id": imdb_id,
                    "wiki_url": wiki_url,
                }

                # Cache the person's details in the database
                self.add_to_cache(person_data, is_movie=False)
                logging.info(
                    f"Successfully fetched and cached details for person: {name}"
                )
                return person_data

        except Exception as e:
            logging.error(f"Error fetching details for person {name}: {e}")
            return {}

    async def fetch_async_with_session(self, session, url):
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logging.error(
                        f"Failed to fetch data from {url}: HTTP status {response.status}"
                    )
                    return None
        except Exception as e:
            logging.error(f"Error during fetch from {url}: {e}")
            return None

    async def get_combined_credits(self, person_id):
        if not self.session:
            self.session = aiohttp.ClientSession()

        search_url = f"https://api.themoviedb.org/3/person/{person_id}/combined_credits?api_key={self.tmdb.api_key}"
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url) as response:
                if response.status == 200:
                    data = await response.text()
                    return json.loads(data)["results"]
                else:
                    return []

    async def get_imdb_id(self, title, max_retries=3, initial_delay=2):
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
        if not self.session:
            self.session = aiohttp.ClientSession()

        """
        Retrieve the Wikipedia URL for a given movie title using Wikimedia API.
        """
        language_code = "en"  # Language code for English Wikipedia
        search_query = title.replace(" ", "%20")

        # Wikipedia API endpoint for search
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={search_query}&format=json"

        try:
            timeout = ClientTimeout(total=60)  # Set a 60 second timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(search_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        search_results = data.get("query", {}).get("search", [])
                        if search_results:
                            page_title = search_results[0]["title"]
                            wiki_url = f"https://{language_code}.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
                            return wiki_url
                        else:
                            return "Wikipedia page not found"
                    else:
                        return "Error in fetching data from Wikipedia"
        except Exception as e:
            return f"Error: {e}"

    def get_related_people(self, movie_details):
        """
        Extract all related people (directors, writers, actors, DoP) from the movie details.
        Returns a list of unique people names.
        """
        people = set()  # Use a set to avoid duplicates

        # Extract the director(s), DoP(s), writer(s), and actor(s)
        # Ensure each entry is a string before adding to the set
        if movie_details.get("director"):
            director = movie_details.get("director")
            if isinstance(director, dict) and "name" in director:
                people.add(director["name"])
            elif isinstance(director, list):
                for d in director:
                    if isinstance(d, dict) and "name" in d:
                        people.add(d["name"])

        if movie_details.get("dop"):
            dop = movie_details.get("dop")
            if isinstance(dop, dict) and "name" in dop:
                people.add(dop["name"])
            elif isinstance(dop, list):
                for d in dop:
                    if isinstance(d, dict) and "name" in d:
                        people.add(d["name"])

        if movie_details.get("writers"):
            writers = movie_details.get("writers")
            if isinstance(writers, list):
                for writer in writers:
                    if isinstance(writer, dict) and "name" in writer:
                        people.add(writer["name"])
            elif isinstance(writers, dict) and "name" in writers:
                people.add(writers["name"])

        if movie_details.get("stars"):
            stars = movie_details.get("stars")
            if isinstance(stars, list):
                for star in stars:
                    if isinstance(star, dict) and "name" in star:
                        people.add(star["name"])
            elif isinstance(stars, dict) and "name" in stars:
                people.add(stars["name"])

        return list(people)

    async def build_data_for_movie(self, movie_title):
        if not self.session:
            self.session = aiohttp.ClientSession()

        print(f"{movie_title.upper()}: Starting data build for movie")
        try:
            # Step 1: Fetch movie details
            movie_search = await self.search_movie(movie_title)
            if not movie_search:
                print(f"{movie_title.upper()}: No search results for movie.")
                return

            movie_id = movie_search[0]["id"]
            movie_details = await self.get_movie_card_details(movie_id)
            if not movie_details:
                print(f"{movie_title.upper()}: No details found for movie.")
                return

            # Step 2: Store fetched movie details in SQLite
            self.add_to_cache(movie_details, is_movie=True)
            print(f"{movie_title.upper()}: Added movie to database.")

            # Step 3: Fetch details for all relevant people (Actors, Directors, Writers, DoP)
            crew_list = self.get_related_people(movie_details)

            # Sequentially process each person
            for person_name in crew_list:
                await self.fetch_person_and_movies(person_name, movie_title.upper())

            print(f"{movie_title.upper()}: Finished data build for movie.")

        except Exception as e:
            logging.error(
                f"{movie_title.upper()}: Failed to fetch details for movie. Error: {e}"
            )
            print(f"{movie_title.upper()}: Error occurred while processing movie: {e}")

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

    async def fetch_person_and_movies(self, person_name, movie_title):
        """
        Fetch movies for a given person if they aren't already present in the database.
        """
        # Check if the person is already in the database before fetching
        print(f"{movie_title}: Checking person in database: {person_name}", flush=True)
        person_details = self.get_from_cache(person_name, is_movie=False)

        if person_details:
            print(
                f"{movie_title}: Person already in database: {person_name}", flush=True
            )
            return  # Exit early if the person is already in the database

        # If person is not in the database, proceed to fetch their details
        print(f"{movie_title}: Fetching details for person: {person_name}", flush=True)
        await self.fetch_person_details(person_name, movie_title)
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

    async def fetch_and_store_movie_details(self, movie_title):
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            # First, check if the movie is already in the database by title
            existing_movie = self.get_from_cache_by_title(movie_title)
            if existing_movie:
                print(
                    f"{movie_title.upper()}: Movie already in database: {existing_movie['title']}"
                )
                return  # No need to fetch if it's already in the database

            # Search for the movie by title to get its ID if not found in the cache
            movie_search_credit = await self.search_movie(movie_title)
            if not movie_search_credit:
                print(f"{movie_title.upper()}: Failed to find movie.")
                return

            movie_id_credit = movie_search_credit[0]["id"]

            # Fetch movie details from the API
            movie_details_credit = await self.get_movie_card_details(movie_id_credit)
            if movie_details_credit:  # Ensure the movie details are not empty
                # Store the movie details in SQLite
                self.add_to_cache(movie_id_credit, movie_details_credit)
                print(f"{movie_title.upper()}: Added movie to database.")
            else:
                print(f"{movie_title.upper()}: No details found for movie.")

        except aiohttp.ClientResponseError as e:
            if e.status == 429 or "rate limit" in str(e).lower():
                print(f"{movie_title.upper()}: Rate limit hit, retrying after delay...")
                await asyncio.sleep(5)  # Introduce a delay before retrying
                await self.fetch_and_store_movie_details(
                    movie_title
                )  # Retry the same movie
            else:
                print(
                    f"{movie_title.upper()}: Error occurred while fetching movie details: {e}"
                )

        except Exception as e:
            print(
                f"{movie_title.upper()}: Error occurred while fetching movie details: {e}"
            )

    async def fetch_person_details(self, star_name, movie_title):
        """
        Fetches details for a person associated with a specific movie title.
        Handles rate limiting and retries if necessary.
        """
        # Ensure the session is initialized
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            # Attempt to fetch the person's details
            person_details = await self.get_person_details(star_name)
            if person_details:
                # Store the fetched details in the SQLite database
                self.add_to_cache(person_details, is_movie=False)
                logging.info(
                    f"{movie_title}: Successfully fetched and added details for person: {star_name}"
                )
                print(f"{movie_title}: Added person to database: {star_name}")
            else:
                logging.warning(
                    f"{movie_title}: No details found for person: {star_name}"
                )
                print(f"{movie_title}: No details found for person: {star_name}")

        except aiohttp.ClientResponseError as e:
            # Handle rate limiting or HTTP 429 errors specifically
            if e.status == 429 or "rate limit" in str(e).lower():
                logging.warning(
                    f"{movie_title}: Rate limit hit for {star_name}, retrying after delay..."
                )
                await asyncio.sleep(5)  # Wait for 5 seconds before retrying
                await self.fetch_person_details(
                    star_name, movie_title
                )  # Retry the request
            else:
                logging.error(
                    f"{movie_title}: HTTP error while fetching details for {star_name}: {e}"
                )
                print(
                    f"{movie_title}: Error occurred while processing person: {star_name}, Error: {e}"
                )

        except Exception as e:
            # Handle any other unexpected exceptions
            logging.error(
                f"{movie_title}: Unexpected error while fetching details for {star_name}: {e}"
            )
            print(
                f"{movie_title}: Error occurred while processing person: {star_name}, Error: {e}"
            )

    def get_main_actors(self, credits, count=5):
        actors = [
            {"name": member["name"], "person_id": member["id"]}
            for member in credits.get("cast", [])
        ][:count]
        return actors if actors else [{"name": "Not Available", "person_id": None}]

    def get_top_writers(self, credits, count=5):
        writers = [
            member["name"]
            for member in credits["crew"]
            if member["department"] == "Writing"
        ][:count]
        return ", ".join(writers) if writers else "Not Available"


# Usage example with DataManager and ConfigManager instances
async def main():
    config_manager = ConfigManager()  # Initialize ConfigManager
    data_manager = DataManager(config_manager)  # Pass ConfigManager to DataManager
    movie_builder = MovieDataBuilder(data_manager)

    # Step 1: Read the list of movie titles from the file
    movie_file = "movies_list.txt"  # File with the list of movies

    try:
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
        print(f"Error occurred: {e}")


# Run the async main function
asyncio.run(main())
