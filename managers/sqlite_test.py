import sqlite3
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def test_database_integrity(db_path="database.db"):
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Movies to check
    movie_titles = ["Tenet", "Interstellar", "The Dark Knight", "Pulp Fiction"]

    # Verify each movie exists in the database
    for title in movie_titles:
        cursor.execute("SELECT * FROM movies WHERE title = ?", (title,))
        movie = cursor.fetchone()
        if movie:
            logging.info(f"Movie '{title}' found in 'movies' table with ID {movie[0]}.")
        else:
            logging.error(f"Movie '{title}' not found in 'movies' table.")

    # Verify cast for each movie
    for title in movie_titles:
        cursor.execute("SELECT tmdb_id FROM movies WHERE title = ?", (title,))
        movie_id = cursor.fetchone()
        if movie_id:
            movie_id = movie_id[0]
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
                logging.info(f"Cast for movie '{title}': {cast}")
            else:
                logging.error(f"No cast found for movie '{title}'.")

    # Verify crew for each movie
    for title in movie_titles:
        cursor.execute("SELECT tmdb_id FROM movies WHERE title = ?", (title,))
        movie_id = cursor.fetchone()
        if movie_id:
            movie_id = movie_id[0]
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
                logging.info(f"Crew for movie '{title}': {crew}")
            else:
                logging.error(f"No crew found for movie '{title}'.")

    # Verify uniqueness in the 'people' table
    cursor.execute(
        """
        SELECT name, COUNT(*) FROM people GROUP BY name HAVING COUNT(*) > 1
    """
    )
    duplicates = cursor.fetchall()
    if duplicates:
        logging.warning(f"Duplicate entries found in 'people' table: {duplicates}")
    else:
        logging.info("No duplicate entries found in 'people' table.")

    # Verify uniqueness in 'movie_crew' (no duplicate roles)
    for title in movie_titles:
        cursor.execute("SELECT tmdb_id FROM movies WHERE title = ?", (title,))
        movie_id = cursor.fetchone()
        if movie_id:
            movie_id = movie_id[0]
            cursor.execute(
                """
                SELECT p.name, mc.job, COUNT(*)
                FROM movie_crew mc
                JOIN people p ON mc.person_id = p.person_id
                WHERE mc.movie_id = ?
                GROUP BY p.name, mc.job
                HAVING COUNT(*) > 1
            """,
                (movie_id,),
            )
            duplicate_roles = cursor.fetchall()
            if duplicate_roles:
                logging.warning(
                    f"Duplicate roles found in 'movie_crew' for '{title}': {duplicate_roles}"
                )
            else:
                logging.info(f"No duplicate roles found in 'movie_crew' for '{title}'.")

    # Verify consistency between 'people' and 'movie_cast'/'movie_crew'
    cursor.execute(
        """
        SELECT mc.person_id FROM movie_cast mc
        LEFT JOIN people p ON mc.person_id = p.person_id
        WHERE p.person_id IS NULL
    """
    )
    missing_cast_links = cursor.fetchall()
    if missing_cast_links:
        logging.error(f"Orphaned cast entries found: {missing_cast_links}")
    else:
        logging.info("All cast entries are correctly linked to 'people'.")

    cursor.execute(
        """
        SELECT mc.person_id FROM movie_crew mc
        LEFT JOIN people p ON mc.person_id = p.person_id
        WHERE p.person_id IS NULL
    """
    )
    missing_crew_links = cursor.fetchall()
    if missing_crew_links:
        logging.error(f"Orphaned crew entries found: {missing_crew_links}")
    else:
        logging.info("All crew entries are correctly linked to 'people'.")

    # Close the database connection
    conn.close()


def test_people_details(db_path="database.db"):
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query all person IDs from the movie_cast and movie_crew tables
    cursor.execute(
        """
        SELECT DISTINCT person_id FROM movie_cast
        UNION
        SELECT DISTINCT person_id FROM movie_crew
    """
    )
    person_ids = cursor.fetchall()

    # Check if each person has their details in the 'people' table
    for (person_id,) in person_ids:
        cursor.execute("SELECT * FROM people WHERE person_id = ?", (person_id,))
        person = cursor.fetchone()
        if person:
            logging.info(f"Person with ID {person_id} has complete details: {person}")
        else:
            logging.error(f"Person with ID {person_id} is missing from 'people' table.")

    # Close the database connection
    conn.close()


if __name__ == "__main__":
    test_database_integrity()
    test_people_details()
