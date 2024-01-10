import json
import os
import logging
import time

# from managers.data_manager import DataManager
import requests
import imdb
from tmdbv3api import TMDb, Movie, Person
import aiohttp
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
        self.tmdb = TMDb()
        self.cache_file = "cache.json"
        self.semaphore = asyncio.Semaphore(3)
        self.session = aiohttp.ClientSession()

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
        async with self.session.get(search_url) as response:  # Use self.session
            if response.status == 200:
                data = await response.text()
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

        # Fetch the movie details asynchronously using the shared session
        details_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={self.tmdb.api_key}&language=en-US"
        credits_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/credits?api_key={self.tmdb.api_key}&language=en-US"

        async with self.session.get(details_url) as details_response, self.session.get(
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

        person_api = Person()
        search_results = person_api.search(name)

        if search_results:
            person_id = search_results[0].id

            # Fetch the person details asynchronously using the shared session
            details_url = f"https://api.themoviedb.org/3/person/{person_id}?api_key={self.tmdb.api_key}&language=en-US"
            async with self.session.get(details_url) as details_response:
                if details_response.status == 200:
                    person_details = await details_response.json()
                else:
                    person_details = {}

            imdb_id = await self.get_imdb_id_for_person(person_details.get("name", ""))
            wiki_url = await self.get_wiki_url(person_details.get("name", ""))

            # Fetch combined credits asynchronously using the shared session
            combined_credits_url = f"https://api.themoviedb.org/3/person/{person_id}/combined_credits?api_key={self.tmdb.api_key}&language=en-US"
            async with self.session.get(combined_credits_url) as credits_response:
                if credits_response.status == 200:
                    combined_credits = await credits_response.json()
                else:
                    combined_credits = {}

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

            # Add the fetched data to the cache
            self.add_to_cache(cache_key, person_data, is_movie=False)
            return person_data

        return {}

    async def get_combined_credits(self, person_id):
        search_url = f"https://api.themoviedb.org/3/person/{person_id}/combined_credits?api_key={self.tmdb.api_key}"

        # Using the shared session for the request
        async with self.session.get(search_url) as response:
            if response.status == 200:
                data = await response.text()
                return json.loads(data)["results"]
            else:
                return []

    async def get_imdb_id(self, title):
        ia = imdb.IMDb()
        loop = asyncio.get_event_loop()
        search_results = await loop.run_in_executor(None, ia.search_movie, title)
        if search_results:
            # Assuming the first search result is the desired one
            return search_results[0].movieID
        return "Not Available"

    async def get_imdb_id_for_person(self, name):
        ia = imdb.IMDb()
        search_results = await asyncio.to_thread(ia.search_person, name)
        if search_results:
            # Assuming the first search result is the desired one
            return search_results[0].personID
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
            # Using the shared session for the request
            async with self.session.get(search_url) as response:
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
        # Ensure actor_name is a valid string
        if not isinstance(actor_name, str):
            logging.error(f"Actor name must be a string. Received: {actor_name}")
            return

        print("Starting data build for actor:", actor_name)
        try:
            # Fetch actor details and check cache
            actor_cache_key = f"person_{actor_name}"
            if actor_cache_key not in self.cache["person_details"]:
                await self.fetch_person_details(actor_name)
                self.save_cache()  # Save cache after fetching actor details
            else:
                print(f"Actor already in cache: {actor_name}")
            actor_details = self.cache["person_details"].get(actor_cache_key)

            semaphore = asyncio.Semaphore(3)  # Limit concurrent fetches

            # Process each movie credit of the actor
            if actor_details:
                actor_movie_tasks = []

                async def limited_movie_fetch(movie_title):
                    async with semaphore:
                        await self.fetch_and_store_movie_details(movie_title)

                for movie in actor_details["movie_credits"]:
                    movie_title = movie.get("title")
                    if movie_title:
                        movie_id = movie.get("id")
                        movie_cache_key = f"movie_card_{movie_id}"
                        if movie_cache_key not in self.cache["movie_details"]:
                            print(f"Processing movie credit: {movie_title}")
                            task = asyncio.create_task(limited_movie_fetch(movie_title))
                            actor_movie_tasks.append(task)
                        else:
                            print(f"Movie already in cache: {movie_title}")

                # Wait for all movie tasks to complete
                await asyncio.gather(*actor_movie_tasks)
                self.save_cache()  # Save cache after processing movie credits

                # Now fetch details for all actors in these movies
                actor_tasks = []

                async def limited_actor_fetch(star_name):
                    async with semaphore:
                        if f"person_{star_name}" not in self.cache["person_details"]:
                            await self.fetch_person_details(star_name)
                        else:
                            print(f"Actor already in cache: {star_name}")

                for movie_key in self.cache["movie_details"]:
                    movie = self.cache["movie_details"][movie_key]
                    for star_name in movie.get("stars", "").split(", "):
                        if star_name:
                            print(f"Checking details for actor: {star_name}")
                            actor_task = asyncio.create_task(
                                limited_actor_fetch(star_name)
                            )
                            actor_tasks.append(actor_task)

                # Wait for all actor tasks to complete
                await asyncio.gather(*actor_tasks)
                print("Finished data build for actors.")
                self.save_cache()  # Save cache after processing actor details

            print("Finished data build for actor:", actor_name)

        except Exception as e:
            logging.error(
                f"Failed to fetch details for actor: {actor_name}. Error: {e}"
            )
            print("Error occurred while processing actor:", actor_name, "Error:", e)

    async def build_data_for_movie(self, movie_title):
        print("Starting data build for movie:", movie_title)
        try:
            movie_search = await self.search_movie(movie_title)
            if movie_search:
                movie_id = movie_search[0]["id"]
                movie_details = await self.get_movie_card_details(movie_id)
                self.cache["movie_details"][f"movie_card_{movie_id}"] = movie_details
                logging.info(f"Successfully fetched details for movie: {movie_title}")

                stars_list = (
                    movie_details.get("stars", "").split(", ")
                    if "stars" in movie_details
                    else []
                )

                # Fetch details for each star, check cache first
                for star_name in stars_list:
                    star_cache_key = f"person_{star_name}"
                    if star_cache_key not in self.cache["person_details"]:
                        await self.fetch_person_details(star_name)

                # Use a semaphore to limit concurrent fetches
                semaphore = asyncio.Semaphore(
                    3
                )  # Adjust the concurrency limit as needed

                async def limited_fetch(movie_title):
                    async with semaphore:
                        await self.fetch_and_store_movie_details(movie_title)

                movie_fetch_tasks = []
                for star_name in stars_list:
                    star_cache_key = f"person_{star_name}"
                    star_details = self.cache["person_details"].get(star_cache_key)
                    if star_details:
                        for credit in star_details["movie_credits"]:
                            movie_title_credit = credit.get("title")
                            movie_id_credit = credit.get("id")
                            cache_key = f"movie_card_{movie_id_credit}"
                            if (
                                movie_title_credit
                                and cache_key not in self.cache["movie_details"]
                            ):
                                print(f"Processing movie credit: {movie_title_credit}")
                                task = asyncio.create_task(
                                    limited_fetch(movie_title_credit)
                                )
                                movie_fetch_tasks.append(task)
                            elif cache_key in self.cache["movie_details"]:
                                print(f"Movie already in cache: {movie_title_credit}")

                await asyncio.gather(*movie_fetch_tasks)
                print("Finished data build.")

                self.save_cache()

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
        # print("Fetching details for person:", star_name)
        try:
            # Await the result of the async function call
            person_details = await self.get_person_details(star_name)

            # Store the result (not the coroutine) in the cache
            self.cache["person_details"][f"person_{star_name}"] = person_details

            logging.info(f"Successfully fetched details for person: {star_name}")

        except Exception as e:
            logging.error(
                f"Failed to fetch details for person: {star_name}. Error: {e}"
            )
            print("Error occurred while processing person:", star_name, "Error:", e)
        await asyncio.sleep(0.15)  # Limit API calls to 10 per second

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

    async def close(self):
        await self.session.close()  # Close the ClientSession


# Usage example with DataManager and ConfigManager instances
# data_manager = DataManager(config_manager)
# movie_builder = MovieDataBuilder(data_manager)
# movie_builder.build_data_for_movie("Inception")
