import sqlite3
import os
import yaml  # For reading the YAML config file
from tmdbv3api import TMDb, Movie, Person
import imdb
import requests
import asyncio
from managers.data_manager import DataManager


class ConfigManager:
    def __init__(self, config_path):
        """Load the configuration file."""
        with open(config_path, "r") as file:
            self.config = yaml.safe_load(file)

    def get_config_value(self, key):
        """Retrieve a config value based on the key."""
        return self.config.get(key)


class MovieDataBuilder:
    def __init__(self, data_manager, config_manager):
        self.data_manager = data_manager
        self.config_manager = config_manager
        self.semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent tasks

        # Load the TMDB API key from the config manager
        self.tmdb_api_key = self.config_manager.get_config_value("tmdb_api_key")
        if not self.tmdb_api_key:
            raise ValueError("TMDB API key is missing from configuration.")

        # Initialize TMDb with the API key
        self.tmdb = TMDb()
        self.tmdb.api_key = self.tmdb_api_key

    def create_tables(self):
        """Create the tables if they don't exist in the database."""
        cursor = self.conn.cursor()

        # Generalized movies table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tmdb_id INTEGER UNIQUE,
                title TEXT NOT NULL,
                description TEXT,
                director_id INTEGER,
                dop_id INTEGER,
                imdb_id TEXT UNIQUE,
                poster_path TEXT,
                release_date DATE,
                vote_average REAL,
                writers TEXT,
                FOREIGN KEY (director_id) REFERENCES people(id),
                FOREIGN KEY (dop_id) REFERENCES people(id)
            )
        """
        )

        # People table (for actors, directors, etc.)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                biography TEXT,
                birthday DATE,
                deathday DATE,
                imdb_id TEXT UNIQUE,
                place_of_birth TEXT,
                profile_path TEXT
            )
        """
        )

        # Junction table for movie-cast relations
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS movie_cast (
                movie_id INTEGER,
                person_id INTEGER,
                role TEXT,
                PRIMARY KEY (movie_id, person_id),
                FOREIGN KEY (movie_id) REFERENCES movies(id),
                FOREIGN KEY (person_id) REFERENCES people(id)
            )
        """
        )

        self.conn.commit()

    def fetch_movie_details(self, title):
        """Fetch movie details from TMDb and insert into the database."""
        # Search for movie by title using TMDb API
        results = self.movie_api.search(title)
        if not results:
            print(f"No results found for movie: {title}")
            return

        movie = results[0]  # Assume the first result is correct
        movie_details = self.movie_api.details(movie.id)
        credits = self.movie_api.credits(movie.id)

        # Insert the movie and people involved (directors, actors, etc.)
        self.insert_movie_and_people(movie_details, credits)

    def insert_movie_and_people(self, movie_details, credits):
        """Insert movie and associated people (director, actors, etc.) into the database."""
        cursor = self.conn.cursor()

        # Insert director, DOP, and writers into `people` table
        director_id = self.insert_person(
            cursor, self.get_crew_member(credits, "Director")
        )
        dop_id = self.insert_person(
            cursor, self.get_crew_member(credits, "Director of Photography")
        )
        writers = ", ".join(
            [
                self.insert_person(cursor, writer)
                for writer in self.get_crew_members(credits, "Writing")
            ]
        )

        # Insert the movie into the `movies` table
        cursor.execute(
            """
            INSERT INTO movies (tmdb_id, title, description, director_id, dop_id, imdb_id, poster_path, release_date, vote_average, writers)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                movie_details.id,
                movie_details.title,
                movie_details.overview,
                director_id,
                dop_id,
                movie_details.imdb_id,
                f"https://image.tmdb.org/t/p/original{movie_details.poster_path}",
                movie_details.release_date,
                movie_details.vote_average,
                writers,
            ),
        )
        movie_id = cursor.lastrowid

        # Insert actors into `people` table and create relations in `movie_cast`
        for actor in credits["cast"]:
            person_id = self.insert_person(cursor, actor)
            cursor.execute(
                """
                INSERT INTO movie_cast (movie_id, person_id, role)
                VALUES (?, ?, ?)
            """,
                (movie_id, person_id, "actor"),
            )

        self.conn.commit()

    def insert_person(self, cursor, person_data):
        """Insert a person into the `people` table, or return their ID if they already exist."""
        if not person_data:
            return None

        cursor.execute(
            "SELECT id FROM people WHERE imdb_id = ?", (person_data["imdb_id"],)
        )
        result = cursor.fetchone()
        if result:
            return result[0]

        # Insert new person if they don't already exist
        cursor.execute(
            """
            INSERT INTO people (name, biography, birthday, deathday, imdb_id, place_of_birth, profile_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                person_data["name"],
                person_data.get("biography", ""),
                person_data.get("birthday", None),
                person_data.get("deathday", None),
                person_data["imdb_id"],
                person_data.get("place_of_birth", ""),
                person_data.get("profile_path", None),
            ),
        )
        return cursor.lastrowid

    def get_crew_member(self, credits, job_title):
        """Return the first crew member matching the job title."""
        for crew_member in credits["crew"]:
            if crew_member["job"] == job_title:
                return crew_member
        return None

    def get_crew_members(self, credits, job_title):
        """Return all crew members matching the job title."""
        return [member for member in credits["crew"] if member["job"] == job_title]


# Usage example
if __name__ == "__main__":
    # Get the directory of the current script file
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "config", "config.yaml")

    # Initialize ConfigManager with the correct config path
    config_manager = ConfigManager(config_path)

    # Get the TMDB API key from the config
    tmdb_key = config_manager.get_config_value("tmdb_api_key")

    # Initialize the MovieDataBuilder with the config's API key
    builder = MovieDataBuilder("data.db", tmdb_key)

    # Fetch movie details for example title
    builder.fetch_movie_details("Inception")
