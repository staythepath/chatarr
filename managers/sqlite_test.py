import sqlite3
import logging

# Set up logging for easier debugging and output viewing
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def connect_to_db(db_path="database.db"):
    """
    Establish a connection to the SQLite database.
    """
    try:
        conn = sqlite3.connect(db_path)
        logging.info(f"Connected to database at {db_path}")
        return conn
    except sqlite3.Error as e:
        logging.error(f"Error connecting to database: {e}")
        return None


def get_movie_details(conn, movie_title):
    """
    Retrieve details of a movie by its title.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tmdb_id, title, description, release_date, vote_average, imdb_id, wiki_url
        FROM movies WHERE title = ?
    """,
        (movie_title,),
    )
    movie = cursor.fetchone()

    if movie:
        movie_details = {
            "TMDb ID": movie[0],
            "Title": movie[1],
            "Description": movie[2],
            "Release Date": movie[3],
            "Vote Average": movie[4],
            "IMDb ID": movie[5],
            "Wikipedia URL": movie[6],
        }
        logging.info(f"Details for movie '{movie_title}': {movie_details}")
        return movie_details
    else:
        logging.warning(f"Movie '{movie_title}' not found in database.")
        return None


def get_movie_cast(conn, movie_id):
    """
    Retrieve the cast for a movie by its TMDb ID.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.name, mc.role FROM movie_cast mc
        JOIN people p ON mc.person_id = p.person_id
        WHERE mc.movie_id = ?
    """,
        (movie_id,),
    )
    cast = cursor.fetchall()

    if cast:
        logging.info(
            f"Cast for movie ID {movie_id}: {[f'{c[0]} as {c[1]}' for c in cast]}"
        )
    else:
        logging.warning(f"No cast found for movie ID {movie_id}.")

    return cast


def get_movie_crew(conn, movie_id):
    """
    Retrieve the crew (director, writer, DOP) for a movie by its TMDb ID.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.name, mc.job FROM movie_crew mc
        JOIN people p ON mc.person_id = p.person_id
        WHERE mc.movie_id = ?
    """,
        (movie_id,),
    )
    crew = cursor.fetchall()

    if crew:
        logging.info(
            f"Crew for movie ID {movie_id}: {[f'{c[0]} as {c[1]}' for c in crew]}"
        )
    else:
        logging.warning(f"No crew found for movie ID {movie_id}.")

    return crew


def get_person_details(conn, person_name):
    """
    Retrieve details of a person by their name.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT person_id, name, biography, birthday, deathday, place_of_birth, imdb_id, wiki_url
        FROM people WHERE name = ?
    """,
        (person_name,),
    )
    person = cursor.fetchone()

    if person:
        person_details = {
            "Person ID": person[0],
            "Name": person[1],
            "Biography": person[2],
            "Birthday": person[3],
            "Deathday": person[4],
            "Place of Birth": person[5],
            "IMDb ID": person[6],
            "Wikipedia URL": person[7],
        }
        logging.info(f"Details for person '{person_name}': {person_details}")
        return person_details
    else:
        logging.warning(f"Person '{person_name}' not found in database.")
        return None


def test_database(conn):
    """
    Test function to check details of 'Interstellar' and 'The Dark Knight' and their respective people.
    """
    # Movies to test
    movies_to_test = ["Interstellar", "The Dark Knight"]
    for movie_title in movies_to_test:
        movie_details = get_movie_details(conn, movie_title)
        if movie_details:
            movie_id = movie_details["TMDb ID"]
            get_movie_cast(conn, movie_id)
            get_movie_crew(conn, movie_id)

    # People to test (directors, DOPs, and notable actors for both movies)
    people_to_test = [
        "Christopher Nolan",
        "Jonathan Nolan",
        "Hans Zimmer",
        "Matthew McConaughey",
        "Anne Hathaway",
        "Michael Caine",
        "Heath Ledger",
        "Wally Pfister",
    ]
    for person_name in people_to_test:
        get_person_details(conn, person_name)


def main():
    conn = connect_to_db()
    if conn:
        test_database(conn)
        conn.close()
        logging.info("Database connection closed.")


if __name__ == "__main__":
    main()
