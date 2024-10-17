import sqlite3
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def count_christopher_nolan_entries(db_path="database.db"):
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query to count entries for Christopher Nolan in the 'people' table
    cursor.execute(
        """
        SELECT COUNT(*) FROM people WHERE name = 'Christopher Nolan'
    """
    )
    people_count = cursor.fetchone()[0]
    logging.info(
        f"Number of entries for Christopher Nolan in 'people' table: {people_count}"
    )

    # Query to count entries for Christopher Nolan in the 'movie_crew' table
    cursor.execute(
        """
        SELECT COUNT(*) FROM movie_crew
        JOIN people ON movie_crew.person_id = people.person_id
        WHERE people.name = 'Christopher Nolan'
    """
    )
    crew_count = cursor.fetchone()[0]
    logging.info(
        f"Number of entries for Christopher Nolan in 'movie_crew' table: {crew_count}"
    )

    # Fetch all entries for Christopher Nolan in the 'movie_crew' table for inspection
    cursor.execute(
        """
        SELECT movie_id, job FROM movie_crew
        JOIN people ON movie_crew.person_id = people.person_id
        WHERE people.name = 'Christopher Nolan'
    """
    )
    crew_entries = cursor.fetchall()
    logging.info(
        f"Details of Christopher Nolan entries in 'movie_crew' table: {crew_entries}"
    )

    # Close the connection
    conn.close()


if __name__ == "__main__":
    count_christopher_nolan_entries()
