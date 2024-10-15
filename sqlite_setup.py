import json
import sqlite3


def create_movies_table(conn):
    """Create the movies table if it doesn't exist."""
    cursor = conn.cursor()
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
            stars TEXT,
            FOREIGN KEY (director_id) REFERENCES people(id),
            FOREIGN KEY (dop_id) REFERENCES people(id)
        )
        """
    )
    conn.commit()


def create_people_table(conn):
    """Create the people table if it doesn't exist."""
    cursor = conn.cursor()
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
            profile_path TEXT,
            movie_credits TEXT  -- This will hold movie IDs as a comma-separated string
        )
        """
    )
    conn.commit()


def create_movie_cast_table(conn):
    """Create the junction table for movie and people relationships."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS movie_cast (
            movie_id INTEGER,
            person_id INTEGER,
            PRIMARY KEY (movie_id, person_id),
            FOREIGN KEY (movie_id) REFERENCES movies(id),
            FOREIGN KEY (person_id) REFERENCES people(id)
        )
        """
    )
    conn.commit()


def insert_movie_record(conn, movie_data):
    """Insert a movie record into the movies table."""
    cursor = conn.cursor()

    # Ensure title is present
    if not movie_data[1]:
        print("Movie title is missing. Skipping insertion.")
        return

    # Look up the director ID
    cursor.execute("SELECT id FROM people WHERE imdb_id = ?", (movie_data[5],))
    director_id = cursor.fetchone()
    director_id = director_id[0] if director_id else None

    # Look up the DOP ID
    cursor.execute("SELECT id FROM people WHERE imdb_id = ?", (movie_data[4],))
    dop_id = cursor.fetchone()
    dop_id = dop_id[0] if dop_id else None

    # Check for existing imdb_id to avoid duplicates
    cursor.execute("SELECT COUNT(*) FROM movies WHERE imdb_id = ?", (movie_data[5],))
    exists = cursor.fetchone()[0]

    if exists:
        print(f"Duplicate found for IMDb ID: {movie_data[5]}. Skipping this entry.")
        return

    # Proceed to insert the movie record
    cursor.execute(
        """
        INSERT INTO movies (tmdb_id, title, description, director_id, dop_id, imdb_id, poster_path, release_date, vote_average, writers, stars)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            movie_data[0],  # tmdb_id
            movie_data[1],  # title
            movie_data[2],  # description
            director_id,  # director_id from people table
            dop_id,  # dop_id from people table
            movie_data[5],  # imdb_id
            movie_data[6],  # poster_path
            movie_data[7],  # release_date
            movie_data[9],  # vote_average
            movie_data[10],  # writers
            movie_data[8],  # stars (string from JSON)
        ),
    )
    movie_id = cursor.lastrowid  # Get the id of the inserted movie record

    # Insert into movie_cast table for stars
    stars = movie_data[8].split(",")  # stars as a comma-separated string
    for star in stars:
        cursor.execute("SELECT id FROM people WHERE imdb_id = ?", (star.strip(),))
        person_id = cursor.fetchone()
        if person_id:
            person_id = person_id[0]
            cursor.execute(
                "INSERT INTO movie_cast (movie_id, person_id) VALUES (?, ?)",
                (movie_id, person_id),
            )

    conn.commit()  # Commit changes after insertion


def insert_person_record(conn, person_data):
    """Insert a person record into the people table."""
    cursor = conn.cursor()

    # Check for existing imdb_id to avoid duplicates
    cursor.execute("SELECT COUNT(*) FROM people WHERE imdb_id = ?", (person_data[5],))
    exists = cursor.fetchone()[0]

    if exists:
        print(f"Duplicate found for IMDb ID: {person_data[5]}. Skipping this entry.")
        return  # Skip the insertion if a duplicate is found

    # Proceed to insert the person record
    cursor.execute(
        """
        INSERT INTO people (name, biography, birthday, deathday, imdb_id, place_of_birth, profile_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        person_data[:7],  # Ensure that only 7 elements are passed
    )
    person_id = cursor.lastrowid  # Get the id of the inserted person record

    # Collect movie credits for this person
    movie_ids = [str(credit["tmdb_id"]) for credit in person_data[7]]
    cursor.execute(
        "UPDATE people SET movie_credits = ? WHERE id = ?",
        (",".join(movie_ids), person_id),
    )

    conn.commit()


def load_movies_from_json(conn, json_file):
    """Load movie data from a JSON file into the database."""
    with open(json_file, "r") as file:
        data = json.load(file)

    # Access the movies in the JSON file
    movies = data.get("movie_details", {})

    for movie_key, movie_info in movies.items():
        movie_data = (
            movie_info.get("tmdb_id"),
            movie_info.get("title"),
            movie_info.get("description"),
            movie_info.get("director"),
            movie_info.get("dop"),
            movie_info.get("imdb_id"),
            movie_info.get("poster_path"),
            movie_info.get("release_date"),
            movie_info.get("stars"),  # Stars from JSON
            movie_info.get("vote_average"),
            movie_info.get("writers"),
        )

        insert_movie_record(conn, movie_data)


def load_people_from_json(conn, json_file):
    """Load people data from a JSON file into the database."""
    with open(json_file, "r") as file:
        data = json.load(file)

    # Access the people in the JSON file
    people = data.get("person_details", {})

    for person_key, person_info in people.items():
        # Check if imdb_id is present
        if not person_info.get("imdb_id"):
            print(f"Skipping person {person_info.get('name')} due to missing IMDb ID.")
            continue  # Skip if imdb_id is missing

        # Extract movie credits safely
        movie_credits = [
            {
                "id": movie["tmdb_id"],  # Check if 'tmdb_id' exists
                "title": movie["title"],
            }
            for movie in person_info.get("movie_credits", [])
            if "tmdb_id" in movie  # Ensure tmdb_id is present
        ]

        person_data = (
            person_info.get("name"),
            person_info.get("biography"),
            person_info.get("birthday"),
            person_info.get("deathday"),
            person_info.get("imdb_id"),
            person_info.get("place_of_birth"),
            person_info.get("profile_path"),
            movie_credits,  # This will pass the list of movie credits
        )

        insert_person_record(conn, person_data)


if __name__ == "__main__":
    # Connect to the database
    conn = sqlite3.connect("database.db")

    # Create the tables
    create_movies_table(conn)
    create_people_table(conn)
    create_movie_cast_table(conn)

    # Load data from the JSON files
    load_movies_from_json(conn, "movies.json")
    load_people_from_json(conn, "people.json")

    # Close the connection
    conn.close()
