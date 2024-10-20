import sqlite3
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Database connection setup
db_path = "database.db"  # Path to your SQLite database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()


def check_movie_existence(movie_title):
    """Check if a movie exists in the database."""
    cursor.execute("SELECT * FROM movies WHERE title = ?", (movie_title,))
    movie = cursor.fetchone()
    if movie:
        logging.info(f"Movie found: {movie_title}")
        return movie  # Return the full movie details
    else:
        logging.error(f"Movie not found: {movie_title}")
        return None


def check_people_existence(person_id):
    """Check if a person exists in the 'people' table."""
    cursor.execute("SELECT * FROM people WHERE person_id = ?", (person_id,))
    person = cursor.fetchone()
    if person:
        return person  # Return person details
    else:
        return None


def display_movie_info(movie):
    """Display the full movie information including cast and crew."""
    tmdb_id = movie[0]  # tmdb_id is the first item in the movie tuple
    logging.info(f"\n\nMovie Info for '{movie[1]}':")
    logging.info(f"TMDB ID: {movie[0]}")
    logging.info(f"Title: {movie[1]}")
    logging.info(f"Description: {movie[2]}")
    logging.info(f"Poster Path: {movie[3]}")
    logging.info(f"Release Date: {movie[4]}")
    logging.info(f"Vote Average: {movie[5]}")
    logging.info(f"IMDB ID: {movie[6]}")
    logging.info(f"Wiki URL: {movie[7]}\n")

    # Display cast for the movie
    logging.info("Cast:")
    cursor.execute(
        "SELECT person_id, role FROM movie_cast WHERE movie_id = ?", (tmdb_id,)
    )
    cast_entries = cursor.fetchall()
    if cast_entries:
        for cast_entry in cast_entries:
            person_id, role = cast_entry
            person = check_people_existence(person_id)
            if person:
                logging.info(f"{person[1]} as {role}")  # person[1] is the name
            else:
                logging.error(f"Person ID {person_id} not found for role '{role}'.")

    # Display crew for the movie
    logging.info("\nCrew:")
    cursor.execute(
        "SELECT person_id, job FROM movie_crew WHERE movie_id = ?", (tmdb_id,)
    )
    crew_entries = cursor.fetchall()
    if crew_entries:
        for crew_entry in crew_entries:
            person_id, job = crew_entry
            person = check_people_existence(person_id)
            if person:
                logging.info(f"{person[1]} - {job}")
            else:
                logging.error(f"Person ID {person_id} not found for job '{job}'.")


def check_cast_and_crew(movie_title):
    """Check if all cast and crew members for a movie are properly stored and referenced."""
    movie = check_movie_existence(movie_title)
    if not movie:
        return  # Movie not found, skip further checks

    display_movie_info(movie)  # Display organized movie info


def check_for_duplicates():
    """Check for duplicate entries in the movie_cast and movie_crew tables."""
    # Check for duplicates in movie_cast
    cursor.execute(
        """
        SELECT movie_id, person_id, role, COUNT(*)
        FROM movie_cast
        GROUP BY movie_id, person_id, role
        HAVING COUNT(*) > 1
    """
    )
    duplicate_cast = cursor.fetchall()
    if duplicate_cast:
        for entry in duplicate_cast:
            logging.error(
                f"Duplicate cast entry found: Movie ID {entry[0]}, Person ID {entry[1]}, Role '{entry[2]}'"
            )
    else:
        logging.info("No duplicate entries found in 'movie_cast'.")

    # Check for duplicates in movie_crew
    cursor.execute(
        """
        SELECT movie_id, person_id, job, COUNT(*)
        FROM movie_crew
        GROUP BY movie_id, person_id, job
        HAVING COUNT(*) > 1
    """
    )
    duplicate_crew = cursor.fetchall()
    if duplicate_crew:
        for entry in duplicate_crew:
            logging.error(
                f"Duplicate crew entry found: Movie ID {entry[0]}, Person ID {entry[1]}, Job '{entry[2]}'"
            )
    else:
        logging.info("No duplicate entries found in 'movie_crew'.")


def check_duplicate_people_across_movies(movies):
    """Check if people are duplicated across multiple movies."""
    logging.info("\nChecking for duplicate people across movies...\n")

    cursor.execute(
        """
        SELECT person_id, COUNT(*) as movie_count
        FROM (
            SELECT person_id FROM movie_cast WHERE movie_id IN (
                SELECT tmdb_id FROM movies WHERE title IN ({})
            )
            UNION
            SELECT person_id FROM movie_crew WHERE movie_id IN (
                SELECT tmdb_id FROM movies WHERE title IN ({})
            )
        )
        GROUP BY person_id
        HAVING movie_count > 1
        """.format(
            ",".join(["?"] * len(movies)), ",".join(["?"] * len(movies))
        ),
        movies * 2,
    )

    duplicate_people = cursor.fetchall()
    if duplicate_people:
        logging.info("Found people who worked on multiple movies:\n")
        for entry in duplicate_people:
            person_id = entry[0]
            person = check_people_existence(person_id)
            if person:
                logging.info(
                    f"Person: {person[1]} (ID: {person_id}) appears in multiple movies."
                )
            else:
                logging.error(f"Person ID {person_id} not found in 'people' table.")
    else:
        logging.info("No duplicate people found across the movies.")


def check_movies():
    """Run all checks for a list of movies."""
    movies = [
        "Inception",
        "Pulp Fiction",
        "The Matrix",
        "The Godfather",
        "The Dark Knight",
        "Interstellar",
        "Dunkirk",
        "Tenet",
        "The Shawshank Redemption",
        "Fight Club",
        "Forrest Gump",
        "Gladiator",
        "Jurassic Park",
        "Schindler's List",
        "Saving Private Ryan",
        "The Lord of the Rings: The Fellowship of the Ring",
    ]

    for movie in movies:
        logging.info(f"Checking movie: {movie}")
        check_cast_and_crew(movie)

    # Check for duplicate entries in cast and crew tables
    check_for_duplicates()

    # Check for duplicate people across multiple movies
    check_duplicate_people_across_movies(movies)


if __name__ == "__main__":
    check_movies()

    # Close the database connection
    conn.close()
