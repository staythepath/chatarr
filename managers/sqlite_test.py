import sqlite3
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def test_database_entries():
    # Connect to the SQLite database
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        # Fetch and display one movie entry
        cursor.execute("SELECT * FROM movies LIMIT 1")
        movie = cursor.fetchone()
        if movie:
            logging.info("\n=== Movie Details ===")
            logging.info(
                f"TMDb ID: {movie[0]}\n\nTitle: {movie[1]}\n\nDescription: {movie[2][:100]}...\n\nPoster Path: {movie[3]}\n\nRelease Date: {movie[4]}\n\nVote Average: {movie[5]}\n\nIMDb ID: {movie[6]}\n\nWiki URL: {movie[7]}\n"
            )

            # Fetch and display movie crew details from the movies table
            directors = movie[8]  # Assuming directors are stored in column index 8
            if directors:
                logging.info(f"\nDirector(s): {directors}\n")
            else:
                logging.warning("No director found in the database.")

            writers = movie[9]  # Assuming writers are stored in column index 9
            if writers:
                logging.info(f"\nWriter(s): {writers}\n")
            else:
                logging.warning("No writer found in the database.")

            dop = movie[10]  # Assuming dop is stored in column index 10
            if dop:
                logging.info(f"\nDirector of Photography (DoP): {dop}\n")
            else:
                logging.warning("No Director of Photography found in the database.")

            # Fetch and display the first 10 actors for the movie
            cursor.execute(
                "SELECT * FROM movie_cast WHERE movie_id = ? LIMIT 10", (movie[0],)
            )
            cast = cursor.fetchall()
            if cast:
                logging.info("\n=== Cast Details ===")
                for actor in cast:
                    cursor.execute(
                        "SELECT * FROM people WHERE person_id = ?", (actor[1],)
                    )
                    person = cursor.fetchone()
                    if person:
                        logging.info(f"Name: {person[1]}\nRole: {actor[2]}\n")
            else:
                logging.warning("No cast found in the database.")
        else:
            logging.warning("No movie found in the database.")

        # Fetch and display one actor
        cursor.execute("SELECT * FROM movie_cast LIMIT 1")
        actor = cursor.fetchone()
        if actor:
            cursor.execute("SELECT * FROM people WHERE person_id = ?", (actor[1],))
            person = cursor.fetchone()
            if person:
                logging.info("\n=== Actor Details ===")
                logging.info(
                    f"Name: {person[1]}\n\nBiography: {' '.join(person[2].split()[:30])}...\n\nBirthday: {person[3]}\n\nDeathday: {person[4]}\n\nPlace of Birth: {person[5]}\n\nProfile Path: {person[6]}\n\nIMDb ID: {person[7]}\n\nWiki URL: {person[8]}\n"
                )
                # Fetch and display credits
                cursor.execute(
                    "SELECT * FROM individual_credits WHERE person_id = ?", (person[0],)
                )
                credits = cursor.fetchall()
                if credits:
                    logging.info("Credits:")
                    for credit in credits:
                        logging.info(f"- {credit[2]} ({credit[3]}) as {credit[4]}")
                else:
                    logging.info("No credits found for this person.")
        else:
            logging.warning("No actor found in the database.")

        logging.info("\n=== Database Test Completed ===\n")

    except Exception as e:
        logging.error(f"Test failed: {e}")
    finally:
        # Close the database connection
        conn.close()


if __name__ == "__main__":
    test_database_entries()
