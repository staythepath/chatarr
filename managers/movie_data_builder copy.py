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
from data_manager import DataManager
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
        self.db_conn = sqlite3.connect("movies.db")  # Connection to the SQLite database
        self.db_cursor = self.db_conn.cursor()
        self.create_tables()

    def create_tables(self):
        """Create tables if they don't already exist."""
        # Create a table for movie details
        self.db_cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS movie_details (
                tmdb_id INTEGER PRIMARY KEY,
                title TEXT,
                director TEXT,
                dop TEXT,
                writers TEXT,
                stars TEXT,
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
            CREATE TABLE IF NOT EXISTS person_details (
                name TEXT PRIMARY KEY,
                biography TEXT,
                birthday TEXT,
                deathday TEXT,
                place_of_birth TEXT,
                profile_path TEXT,
                movie_credits TEXT,
                imdb_id TEXT,
                wiki_url TEXT
            )
        """
        )
        self.db_conn.commit()  # Save changes

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

    def add_to_cache(self, key, data, is_movie=True):
        if is_movie:
            self.db_cursor.execute(
                """
                INSERT OR REPLACE INTO movie_details 
                (tmdb_id, title, director, dop, writers, stars, description, poster_path, release_date, vote_average, imdb_id, wiki_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["tmdb_id"],
                    data["title"],
                    data["director"],
                    data["dop"],
                    data["writers"],
                    data["stars"],
                    data["description"],
                    data["poster_path"],
                    data["release_date"],
                    data["vote_average"],
                    data["imdb_id"],
                    data["wiki_url"],
                ),
            )
        else:
            self.db_cursor.execute(
                """
                INSERT OR REPLACE INTO person_details 
                (name, biography, birthday, deathday, place_of_birth, profile_path, movie_credits, imdb_id, wiki_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["name"],
                    data["biography"],
                    data["birthday"],
                    data["deathday"],
                    data["place_of_birth"],
                    data["profile_path"],
                    json.dumps(data["movie_credits"]),
                    data["imdb_id"],
                    data["wiki_url"],
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
            return cached_data

        # If not found in cache, fetch the data from the API
        async with aiohttp.ClientSession() as session:
            details_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={self.tmdb.api_key}&language=en-US"
            credits_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/credits?api_key={self.tmdb.api_key}&language=en-US"

            async with session.get(details_url) as details_response, session.get(
                credits_url
            ) as credits_response:
                if details_response.status == 200 and credits_response.status == 200:
                    movie = await details_response.json()
                    credits = await credits_response.json()
                else:
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

            # Add the fetched data to the cache (SQLite)
            self.add_to_cache(cache_key, movie_card_data)
            return movie_card_data

    def get_from_cache(self, key, is_movie=True):
        if is_movie:
            self.db_cursor.execute(
                "SELECT * FROM movie_details WHERE tmdb_id = ?", (key,)
            )
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
        else:
            self.db_cursor.execute(
                "SELECT * FROM person_details WHERE name = ?", (key,)
            )
            person = self.db_cursor.fetchone()
            if person:
                return {
                    "name": person[0],
                    "biography": person[1],
                    "birthday": person[2],
                    "deathday": person[3],
                    "place_of_birth": person[4],
                    "profile_path": person[5],
                    "movie_credits": json.loads(
                        person[6]
                    ),  # Convert JSON string back to object
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
        cache_key = f"person_{name}"
        cached_data = self.get_from_cache(cache_key, is_movie=False)

        if not self.session:
            self.session = aiohttp.ClientSession()

        if cached_data:
            return cached_data

        try:
            person_api = Person()
            search_results = person_api.search(name)
            if not search_results:
                return {}

            person_id = search_results[0].id
            async with aiohttp.ClientSession() as session:
                details_url = f"https://api.themoviedb.org/3/person/{person_id}?api_key={self.tmdb.api_key}&language=en-US"
                person_details = await self.fetch_async_with_session(
                    session, details_url
                )
                if not person_details:
                    return {}

                imdb_id = await self.get_imdb_id_for_person(
                    person_details.get("name", "")
                )
                wiki_url = await self.get_wiki_url(person_details.get("name", ""))

                combined_credits_url = f"https://api.themoviedb.org/3/person/{person_id}/combined_credits?api_key={self.tmdb.api_key}&language=en-US"
                combined_credits = await self.fetch_async_with_session(
                    session, combined_credits_url
                )
                credits_info = self.process_combined_credits(combined_credits)

            # Combine the details and credits to return a single response
            person_data = {
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

            self.add_to_cache(cache_key, person_data, is_movie=False)
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
        if movie_details.get("director"):
            directors = movie_details.get("director").split(", ")
            people.update(directors)

        if movie_details.get("dop"):
            dop = movie_details.get("dop").split(", ")
            people.update(dop)

        if movie_details.get("writers"):
            writers = movie_details.get("writers").split(", ")
            people.update(writers)

        if movie_details.get("stars"):
            stars = movie_details.get("stars").split(", ")
            people.update(stars)

        return list(people)

    async def build_data_for_movie(self, movie_title):
        if not self.session:
            self.session = aiohttp.ClientSession()

        print("Starting data build for movie:", movie_title)
        try:
            # Step 1: Fetch movie details
            movie_search = await self.search_movie(movie_title)
            if not movie_search:
                print(f"No search results for movie: {movie_title}")
                return

            movie_id = movie_search[0]["id"]
            movie_details = await self.get_movie_card_details(movie_id)
            if not movie_details:
                print(f"No details found for movie: {movie_title}")
                return

            # Step 2: Store fetched movie details in SQLite
            self.add_to_cache(movie_id, movie_details, is_movie=True)
            print(f"Added movie to database: {movie_title}")

            # Step 3: Fetch details for all relevant people (Actors, Directors, Writers, DoP)
            crew_list = self.get_related_people(movie_details)

            # Sequentially process each person
            for person_name in crew_list:
                await self.fetch_person_and_movies(person_name)

            print(f"Finished data build for movie: {movie_title}")

        except Exception as e:
            logging.error(
                f"Failed to fetch details for movie: {movie_title}. Error: {e}"
            )
            print("Error occurred while processing movie:", movie_title, "Error:", e)

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

    async def fetch_person_and_movies(self, person_name):
        print(f"Fetching movies for person: {person_name}", flush=True)

        # Fetch person details if not already in the database
        person_details = self.get_from_cache(person_name, is_movie=False)

        if not person_details:
            await self.fetch_person_details(person_name)
            print(f"Fetched and added person to database: {person_name}", flush=True)
        else:
            print(f"Person already in database: {person_name}", flush=True)

        # Fetch and store their other movie credits (but no recursion)
        star_details = self.get_from_cache(person_name, is_movie=False)
        if star_details:
            movie_fetch_tasks = []  # Collect tasks for fetching each movie
            for credit in star_details.get("movie_credits", []):
                movie_title_credit = credit.get("title")

                # Check if the movie is already in the database by title
                if self.get_from_cache_by_title(movie_title_credit):
                    print(f"Movie already in database: {movie_title_credit}")
                    continue  # Skip fetching if already in the database

                print(
                    f"Fetching movie '{movie_title_credit}' for person: {person_name}",
                    flush=True,
                )
                movie_fetch_tasks.append(
                    self.fetch_and_store_movie_details(movie_title_credit)
                )

            # Limit concurrent movie fetch tasks and avoid overwhelming the API
            semaphore = asyncio.Semaphore(3)  # Adjust the semaphore value as necessary

            async with semaphore:
                await asyncio.gather(
                    *movie_fetch_tasks
                )  # Fetch movie details concurrently

            print(f"Finished fetching movies for person: {person_name}", flush=True)

    async def fetch_and_store_movie_details(self, movie_title):
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            # First, check if the movie is already in the database by title
            existing_movie = self.get_from_cache_by_title(movie_title)
            if existing_movie:
                print(f"Movie already in database: {existing_movie['title']}")
                return  # No need to fetch if it's already in the database

            # Search for the movie by title to get its ID if not found in the cache
            movie_search_credit = await self.search_movie(movie_title)
            if not movie_search_credit:
                print(f"Failed to find movie: {movie_title}")
                return

            movie_id_credit = movie_search_credit[0]["id"]

            # Fetch movie details from the API
            movie_details_credit = await self.get_movie_card_details(movie_id_credit)
            if movie_details_credit:  # Ensure the movie details are not empty
                # Store the movie details in SQLite
                self.add_to_cache(movie_id_credit, movie_details_credit, is_movie=True)
                print(f"Added movie to database: {movie_title}")
            else:
                print(f"No details found for movie: {movie_title}")

        except aiohttp.ClientResponseError as e:
            if e.status == 429 or "rate limit" in str(e).lower():
                print(f"Rate limit hit for {movie_title}, retrying after delay...")
                await asyncio.sleep(5)  # Introduce a delay before retrying
                await self.fetch_and_store_movie_details(
                    movie_title
                )  # Retry the same movie
            else:
                print(
                    f"Error occurred while fetching movie details for {movie_title}: {e}"
                )

        except Exception as e:
            print(f"Error occurred while fetching movie details for {movie_title}: {e}")

    async def fetch_person_details(self, star_name):
        if not self.session:
            self.session = aiohttp.ClientSession()

        try:
            person_details = await self.get_person_details(star_name)
            if person_details:
                # Store person details in SQLite instead of cache
                self.add_to_cache(star_name, person_details, is_movie=False)
                logging.info(
                    f"Successfully fetched and added details for person: {star_name}"
                )
                print(f"Added person to database: {star_name}")
            else:
                print(f"No details found for person: {star_name}")
        except Exception as e:
            # Check for rate limiting in the exception message or response
            if (
                "rate limit" in str(e).lower()
                or isinstance(e, aiohttp.ClientResponseError)
                and e.status == 429
            ):
                logging.warning("Rate limit hit, pausing for 5 seconds")
                await asyncio.sleep(5)  # Pause for 5 seconds
                return await self.fetch_person_details(star_name)  # Retry the request
            else:
                logging.error(
                    f"Failed to fetch details for person: {star_name}. Error: {e}"
                )
                print(
                    f"Error occurred while processing person: {star_name}, Error: {e}"
                )

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


# Usage example with DataManager and ConfigManager instances
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

        print("Got past with")
        print(f"MovieTitles: ", movie_titles)
        # Step 2: Loop through each movie and build data one at a time
        for movie_title in movie_titles:
            print("Looping through titles")
            print(f"Processing movie: {movie_title}")
            await movie_builder.build_data_for_movie(
                movie_title
            )  # Process one movie at a time
            print(f"Finished processing movie: {movie_title}")

    except Exception as e:
        print(f"Error occurred: {e}")


# Run the async main function
asyncio.run(main())


# Ensure the database connection is properly closed
def __del__(self):
    if self.db_conn:
        self.db_conn.close()
