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


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class MovieDataBuilder:
    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.cache = {"movie_details": {}, "person_details": {}}
        self.load_cache()
        self.tmdb = TMDb()  # Initialize the 'tmdb' attribute
        self.cache_file = "cache.json"
        self.semaphore = asyncio.Semaphore(3)  # Limit to 5 concurrent tasks
        self.session = aiohttp.ClientSession()  # Create a shared session

    def is_json_serializable(data):
        try:
            json.dumps(data)
            return True
        except (TypeError, OverflowError):
            return False

    def load_cache(self):
        cache_file = "cache.json"
        if os.path.exists(cache_file):
            with open(cache_file, "r") as file:
                try:
                    self.cache = json.load(file)
                except json.JSONDecodeError:
                    self.cache = {"movie_details": {}, "person_details": {}}
        else:
            self.cache = {"movie_details": {}, "person_details": {}}

    def save_cache(self):
        with open("cache.json", "w") as file:
            json.dump(self.cache, file, indent=4)

    async def search_movie(self, title):
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
        if self.is_json_serializable(data):
            category = "movie_details" if is_movie else "person_details"
            self.cache[category][key] = data
            self.save_cache_to_file()  # Save updated cache to file
        else:
            logging.error(f"Data for key {key} is not JSON serializable")

    def save_cache_to_file(self):
        """Save the current state of the cache to a JSON file with pretty-printing."""
        with open(self.cache_file, "w") as file:
            json.dump(self.cache, file, indent=4, sort_keys=True)

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
        cached_data = self.get_from_cache(cache_key, is_movie=True)

        if cached_data:
            return cached_data

        async with aiohttp.ClientSession() as session:
            # Fetch the movie details asynchronously
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
                "poster_path": f"https://image.tmdb.org/t/p/original{movie.get('poster_path', '')}"
                if movie.get("poster_path")
                else None,
                "release_date": movie.get("release_date", ""),
                "vote_average": movie.get("vote_average", ""),
                "imdb_id": imdb_id,
                "wiki_url": wiki_url,
            }

            # Add the fetched data to the cache
            self.add_to_cache(cache_key, movie_card_data)
            return movie_card_data

    def get_from_cache(self, key, is_movie=True):
        """Retrieve an item from the cache if it exists."""
        category = "movie_details" if is_movie else "person_details"
        return self.cache[category].get(key)

    def get_crew_member(self, credits, job_title):
        for crew_member in credits["crew"]:
            if crew_member["job"] == job_title:
                return crew_member["name"]
        return "Not Available"

    async def get_person_details(self, name):
        cache_key = f"person_{name}"
        cached_data = self.get_from_cache(cache_key, is_movie=False)

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
        search_url = f"https://api.themoviedb.org/3/person/{person_id}/combined_credits?api_key={self.tmdb.api_key}"
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url) as response:
                if response.status == 200:
                    data = await response.text()
                    return json.loads(data)["results"]
                else:
                    return []

    async def get_imdb_id(self, title, max_retries=3, initial_delay=2):
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

    async def build_data_for_people(self, actor_name):
        try:
            if not isinstance(actor_name, str):
                raise ValueError(f"Actor name must be a string. Received: {actor_name}")

            logging.info("Starting data build for actor: %s", actor_name)

            actor_cache_key = f"person_{actor_name}"
            if actor_cache_key not in self.cache["person_details"]:
                actor_fetched = await self.fetch_person_details(actor_name)
                if not actor_fetched:
                    logging.warning(f"No details found for actor: {actor_name}")
                    return  # Skip further processing for this actor, but continue with others
                self.save_cache()
            else:
                logging.info(f"Actor already in cache: {actor_name}")

            actor_details = self.cache["person_details"].get(actor_cache_key)
            if not actor_details:
                logging.warning(f"Actor details not found in cache: {actor_name}")
                return  # Skip to the next actor

            semaphore = asyncio.Semaphore(3)  # Limit concurrent fetches

            if actor_details:
                actor_movie_tasks = []

                async def limited_movie_fetch(movie_title):
                    try:
                        async with semaphore:
                            await self.fetch_and_store_movie_details(movie_title)
                    except KeyError as ke:
                        logging.error(f"KeyError in fetching movie details: {ke}")
                    except asyncio.TimeoutError as te:
                        logging.error(f"Timeout error in fetching movie details: {te}")
                    except Exception as e:
                        logging.error(
                            f"Unexpected error in fetching movie details: {e}"
                        )

                for movie in actor_details.get("movie_credits", []):
                    movie_title = movie.get("title")
                    if movie_title:
                        movie_id = movie.get("id")
                        movie_cache_key = f"movie_card_{movie_id}"
                        if movie_cache_key not in self.cache["movie_details"]:
                            # print(f"Processing movie credit: {movie_title}")
                            logging.info(
                                f"Processing movie credit: {movie_title}"
                            )  # Add logging statement
                            task = asyncio.create_task(limited_movie_fetch(movie_title))
                            actor_movie_tasks.append(task)
                        else:
                            # print(f"Movie already in cache: {movie_title}")
                            logging.info(
                                f"Movie already in cache: {movie_title}"
                            )  # Add logging statement

                await asyncio.gather(*actor_movie_tasks)
                self.save_cache()  # Save cache after processing movie credits

                actor_tasks = []

                async def limited_actor_fetch(star_name):
                    try:
                        async with semaphore:
                            if (
                                f"person_{star_name}"
                                not in self.cache["person_details"]
                            ):
                                await self.fetch_person_details(star_name)
                            else:
                                # print(f"Actor already in cache: {star_name}")
                                logging.info(
                                    f"Actor already in cache: {star_name}"
                                )  # Add logging statement
                    except KeyError as ke:
                        logging.error(f"KeyError in fetching actor details: {ke}")
                    except asyncio.TimeoutError as te:
                        logging.error(f"Timeout error in fetching actor details: {te}")
                    except Exception as e:
                        logging.error(
                            f"Unexpected error in fetching actor details: {e}"
                        )

                for movie_key in self.cache["movie_details"]:
                    movie = self.cache["movie_details"][movie_key]
                    for star_name in movie.get("stars", "").split(", "):
                        if star_name:
                            # print(f"Checking details for actor: {star_name}")
                            logging.info(
                                f"Checking details for actor: {star_name}"
                            )  # Add logging statement
                            actor_task = asyncio.create_task(
                                limited_actor_fetch(star_name)
                            )
                            actor_tasks.append(actor_task)

                await asyncio.gather(*actor_tasks)
                logging.info("Finished data build for actors.")  # Add logging statement
                self.save_cache()

            # print("Finished data build for actor:", actor_name)
            logging.info(
                "Finished data build for actor: %s", actor_name
            )  # Add logging statement

        except ValueError as ve:
            logging.error(f"ValueError: {ve}")
            print(
                f"ValueError occurred while processing actor: {actor_name}. Error: {ve}"
            )
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            print(f"Error occurred while processing actor: {actor_name}. Error: {e}")

    async def build_data_for_movie(self, movie_title):
        print("Starting data build for movie:", movie_title)
        try:
            movie_search = await self.search_movie(movie_title)
            print(
                "Here is the movie_search:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::: ",
                movie_search,
            )
            if not movie_search:
                print(f"No search results for movie: {movie_title}")
                return

            movie_id = movie_search[0]["id"]
            movie_details = await self.get_movie_card_details(movie_id)
            if not movie_details:
                print(f"No details found for movie: {movie_title}")
                return

            self.cache["movie_details"][f"movie_card_{movie_id}"] = movie_details
            logging.info(f"Successfully fetched details for movie: {movie_title}")

            stars_list = (
                movie_details.get("stars", "").split(", ")
                if "stars" in movie_details
                else []
            )
            person_fetch_tasks = []
            semaphore = asyncio.Semaphore(4)  # Limit concurrent fetches

            async def fetch_person_and_movie_details(star_name):
                star_cache_key = f"person_{star_name}"
                if star_cache_key not in self.cache["person_details"]:
                    await self.fetch_person_details(star_name)
                else:
                    print(f"Actor already in cache: {star_name}")

                # Fetch and store movie details
                star_details = self.cache["person_details"].get(star_cache_key)
                for credit in star_details.get("movie_credits", []):
                    movie_title_credit = credit.get("title")
                    movie_id_credit = credit.get("id")
                    cache_key = f"movie_card_{movie_id_credit}"
                    if (
                        movie_title_credit
                        and cache_key not in self.cache["movie_details"]
                    ):
                        # print(f"Processing movie credit: {movie_title_credit}")
                        async with semaphore:
                            await self.fetch_and_store_movie_details(movie_title_credit)
                    else:
                        print(f"Movie already in cache: {movie_title_credit}")

            for star_name in stars_list:
                person_fetch_task = asyncio.create_task(
                    fetch_person_and_movie_details(star_name)
                )
                person_fetch_tasks.append(person_fetch_task)

            # Wait for all tasks to complete
            await asyncio.gather(*person_fetch_tasks)
            self.save_cache()
            print(f"Finished data build for movie: {movie_title}")

        except Exception as e:
            logging.error(
                f"Failed to fetch details for movie: {movie_title}. Error: {e}"
            )
            print("Error occurred while processing movie:", movie_title, "Error:", e)

    async def fetch_and_store_movie_details(self, movie_title):
        try:
            movie_search_credit = await self.search_movie(movie_title)
            if movie_search_credit:
                movie_id_credit = movie_search_credit[0]["id"]
                cache_key = f"movie_card_{movie_id_credit}"
                if cache_key not in self.cache["movie_details"]:
                    movie_details_credit = await self.get_movie_card_details(
                        movie_id_credit
                    )
                    if movie_details_credit:  # Ensure the movie details are not empty
                        self.cache["movie_details"][cache_key] = movie_details_credit
                        print(f"Added movie to cache: {movie_title}")
                    else:
                        print(f"No details found for movie: {movie_title}")
                else:
                    print(f"Movie already in cache: {movie_title}")
            else:
                print(f"Failed to find movie: {movie_title}")
        except Exception as e:
            print(f"Error occurred while fetching movie details for {movie_title}: {e}")

    async def fetch_person_details(self, star_name):
        try:
            person_details = await self.get_person_details(star_name)
            self.cache["person_details"][f"person_{star_name}"] = person_details
            logging.info(f"Successfully fetched details for person: {star_name}")
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
                print("Error occurred while processing person:", star_name, "Error:", e)
        await asyncio.sleep(0.7)  # Regular delay between API calls

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
# data_manager = DataManager(config_manager)
# movie_builder = MovieDataBuilder(data_manager)
# movie_builder.build_data_for_movie("Inception")
