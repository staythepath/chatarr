import sqlite3


def fetch_people_worked_on_movie(movie_title):
    """
    Fetch people (actors, directors, writers, DoP) who worked on a specific movie.
    """
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()

    # Query for the movie in the movie_details table
    cursor.execute("SELECT * FROM movie_details WHERE title = ?", (movie_title,))
    movie = cursor.fetchone()

    if not movie:
        print(f"No movie found with the title: {movie_title}")
        conn.close()
        return

    print(f"People who worked on '{movie_title}':")

    # Extract related people (actors, directors, DoP, writers)
    director, dop, writers, stars = movie[2], movie[3], movie[4], movie[5]

    people = set()
    if director:
        people.update(director.split(", "))
    if dop:
        people.update(dop.split(", "))
    if writers:
        people.update(writers.split(", "))
    if stars:
        people.update(stars.split(", "))

    # Print the people and query for movies they've worked on
    for person in people:
        print(f"\n{person}:")
        fetch_movies_by_person(person)

    conn.close()


def fetch_movies_by_person(person_name):
    """
    Fetch movies related to a specific person (actor, director, etc.)
    """
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()

    # Query for the person in the person_details table
    cursor.execute("SELECT * FROM person_details WHERE name = ?", (person_name,))
    person = cursor.fetchone()

    if not person:
        print(f"No details found for person: {person_name}")
        return

    # Fetch and print the movies they have worked on
    print(f"Movies featuring or related to {person_name}:")
    movie_credits = person[6]  # Movie credits stored as JSON string
    if movie_credits:
        movies = eval(movie_credits)  # Convert JSON string to list
        for movie in movies:
            print(f" - {movie['title']} ({movie['release_year']})")

    conn.close()


def main():
    # Change this to any movie you want to check
    movie_title = "Inception"
    fetch_people_worked_on_movie(movie_title)


if __name__ == "__main__":
    main()
