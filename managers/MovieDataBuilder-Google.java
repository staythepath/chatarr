import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import com.google.gson.JsonParser;
import com.google.gson.stream.JsonReader;
import com.tmdb.api.TmdbApi;
import com.tmdb.model.*;
import org.asynchttpclient.AsyncHttpClient;
import org.asynchttpclient.DefaultAsyncHttpClientConfig;
import org.asynchttpclient.Dsl;
import org.asynchttpclient.Response;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.scheduling.annotation.Async;
import org.springframework.scheduling.annotation.AsyncResult;
import org.springframework.stereotype.Service;

import java.io.StringReader;
import java.util.*;
import java.util.concurrent.Future;

@Service
public class MovieDataBuilder implements ApplicationRunner {

    private static final Logger LOGGER = LoggerFactory.getLogger(MovieDataBuilder.class);

    @Value("${the-movie-db.api-key}")
    private String tmdbApiKey;

    @Autowired
    private AsyncHttpClient asyncHttpClient;

    @Autowired
    private TmdbApi tmdbApi;

    @Override
    public void run(ApplicationArguments args) {
        String movieTitle = "Inception";
        buildDataForMovie(movieTitle);
    }

    public void buildDataForMovie(String movieTitle) {
        LOGGER.info("Starting data build for movie: " + movieTitle);
        try {
            Search movieSearch = tmdbApi.getSearch().searchMovie(movieTitle, 1).execute();
            if (movieSearch.getResults().isEmpty()) {
                LOGGER.info("No search results for movie: " + movieTitle);
                return;
            }

            Movie movie = tmdbApi.getMovies().getMovie(movieSearch.getResults().get(0).getId(), null).execute();
            MovieDetails movieDetails = getMovieDetails(movie);
            LOGGER.info("Successfully fetched details for movie: " + movieTitle);

            List<String> starsList = Arrays.asList(movieDetails.getStars().split(", "));
            fetchPersonDetails(starsList);

            // Fetch and store movie details for credits
            for (MovieCredit movieCredit : movieDetails.getMovieCredits()) {
                String movieTitleCredit = movieCredit.getTitle();
                Integer movieIdCredit = movieCredit.getId();
                String cacheKey = "movie_card_" + movieIdCredit;
                if (!movieCache.containsKey(cacheKey)) {
                    LOGGER.info("Processing movie credit: " + movieTitleCredit);
                    MovieDetails movieDetailsCredit = getMovieDetails(tmdbApi.getMovies().getMovie(movieIdCredit, null).execute());
                    movieCache.put(cacheKey, movieDetailsCredit);
                } else {
                    LOGGER.info("Movie already in cache: " + movieTitleCredit);
                }
            }

        } catch (Exception e) {
            LOGGER.error("Failed to fetch details for movie: " + movieTitle + ". Error: " + e);
        }

        LOGGER.info("Finished data build for movie: " + movieTitle);
    }

    @Async
    public void fetchPersonDetails(List<String> personNames) {
        List<Future<PersonDetails>> personDetailsFutures = new ArrayList<>();

        for (String personName : personNames) {
            Future<PersonDetails> personDetailsFuture = AsyncResult.forValue(getPersonDetails(personName));
            personDetailsFutures.add(personDetailsFuture);
        }

        try {
            List<PersonDetails> personDetailsList = new ArrayList<>();
            for (Future<PersonDetails> personDetailsFuture : personDetailsFutures) {
                personDetailsList.add(personDetailsFuture.get());
            }

            // Update movie details with person details
            for (MovieDetails movieDetails : movieCache.values()) {
                List<MovieCredit> updatedMovieCredits = new ArrayList<>();
                for (MovieCredit movieCredit : movieDetails.getMovieCredits()) {
                    for (PersonDetails personDetails : personDetailsList) {
                        if (personDetails.getName().equals(movieCredit.getActor())) {
                            movieCredit.setPersonDetails(personDetails);
                            break;
                        }
                    }
                    updatedMovieCredits.add(movieCredit);
                }
                movieDetails.setMovieCredits(updatedMovieCredits);
            }
        } catch (Exception e) {
            LOGGER.error("Error occurred while fetching person details: " + e);
        }

        LOGGER.info("Finished data build for actors.");
    }

    private MovieDetails getMovieDetails(Movie movie) {
        String tmdbId = String.valueOf(movie.getId());
        String cacheKey = "movie_card_" + tmdbId;

        if (!movieCache.containsKey(cacheKey)) {
            MovieDetails movieDetails = new MovieDetails();
            movieDetails.setTmdbId(tmdbId);
            movieDetails.setTitle(movie.getTitle());
            movieDetails.setDirector(getCrewMember(movie.getCredits(), "Director"));
            movieDetails.setDop(getCrewMember(movie.getCredits(), "Director of Photography"));
            movieDetails.setWriters(getTopWriters(movie.getCredits()));
            movieDetails.setStars(getMainActors(movie.getCredits()));
            movieDetails.setDescription(movie.getOverview());
            movieDetails.setPosterPath(movie.getPosterPath());
            movieDetails.setReleaseDate(movie.getReleaseDate());
            movieDetails.setVoteAverage(movie.getVoteAverage());
            movieDetails.setImdbId(getImdbId(movie.getTitle()));
            movieDetails.setWikiUrl(getWikiUrl(movie.getTitle()));

            movieCache.put(cacheKey, movieDetails);
        }

        return movieCache.get(cacheKey);
    }

    private PersonDetails getPersonDetails(String personName) {
        String cacheKey = "person_" + personName;

        if (!personCache.containsKey(cacheKey)) {
            Person person = tmdbApi.getPeople().getPerson(personName, null).execute();

            PersonDetails personDetails = new PersonDetails();
            personDetails.setName(person.getName());
            personDetails.setBiography(person.getBiography());
            personDetails.setBirthday(person.getBirthday());
            personDetails.setDeathday(person.getDeathday());
            personDetails.setPlaceOfBirth(person.getPlaceOfBirth());
            personDetails.setProfilePath(person.getProfilePath());
            personDetails.setMovieCredits(getCombinedCredits(person.getId()));

            personCache.put(cacheKey, personDetails);
        }

        return personCache.get(cacheKey);
    }

    private List<MovieCredit> getCombinedCredits(Integer personId) {
        List<MovieCredit> movieCredits = new ArrayList<>();

        Credits combinedCredits = tmdbApi.getPeople().getCombinedCredits(personId, null).execute();

        for (CombinedCredit combinedCredit : combinedCredits.getCast()) {
            if (combinedCredit.getReleaseDate() != null
                    && !featureFilmGenreIds.isdisjoint(Set.copyOf(combinedCredit.getGenreIds()))
                    && combinedCredit.getVoteCount() >= minVoteCount) {
                MovieCredit movieCredit = new MovieCredit();
                movieCredit.setTitle(combinedCredit.getTitle());
                movieCredit.setReleaseYear(combinedCredit.getReleaseDate().substring(0, 4));
                movieCredit.setPopularity(combinedCredit.getPopularity());
                movieCredit.setVoteAverage(combinedCredit.getVoteAverage());
                movieCredit.setActor(combinedCredit.getCharacter());

                movieCredits.add(movieCredit);
            }
        }

        for (CombinedCredit combinedCredit : combinedCredits.getCrew()) {
            if (combinedCredit.getJob().equals("Director")
                    && combinedCredit.getReleaseDate() != null
                    && combinedCredit.getVoteCount() >= minVoteCount) {
                MovieCredit movieCredit = new MovieCredit();
                movieCredit.setTitle(combinedCredit.getTitle());
                movieCredit.setReleaseYear(combinedCredit.getReleaseDate().substring(0, 4));
                movieCredit.setPopularity(combinedCredit.getPopularity());
                movieCredit.setVoteAverage(combinedCredit.getVoteAverage());
                movieCredit.setActor(combinedCredit.getJob());

                movieCredits.add(movieCredit);
            }
        }

        Collections.sort(movieCredits, (mc1, mc2) -> {
            int yearComparison = mc2.getReleaseYear().compareTo(mc1.getReleaseYear());
            if (yearComparison == 0) {
                return mc2.getPopularity().compareTo(mc1.getPopularity());
            }
            return yearComparison;
        });

        return movieCredits;
    }

    private MovieDetails buildMovieDetails(Movie movie, Map<String, PersonDetails> personMap) {
        MovieDetails movieDetails = new MovieDetails();
        movieDetails.setTmdbId(String.valueOf(movie.getId()));
        movieDetails.setTitle(movie.getTitle());
        movieDetails.setDirector(getCrewMember(movie.getCredits(), "Director"));
        movieDetails.setDop(getCrewMember(movie.getCredits(), "Director of Photography"));
        movieDetails.setWriters(getTopWriters(movie.getCredits()));
        movieDetails.setStars(getMainActors(movie.getCredits()));
        movieDetails.setDescription(movie.getOverview());
        movieDetails.setPosterPath(movie.getPosterPath());
        movieDetails.setImdbId(getImdbId(movie.getTitle()));
        movieDetails.setWikiUrl(getWikiUrl(movie.getTitle()));
        movieDetails.setReleaseDate(movie.getReleaseDate());
        movieDetails.setVoteAverage(movie.getVoteAverage());

        // Add person details to movie credits
        List<MovieCredit> movieCredits = new ArrayList<>();
        for (MovieCredit movieCredit : movieDetails.getMovieCredits()) {
            MovieCredit updatedMovieCredit = new MovieCredit();
            updatedMovieCredit.setTitle(movieCredit.getTitle());
            updatedMovieCredit.setReleaseYear(movieCredit.getReleaseYear());
            updatedMovieCredit.setPopularity(movieCredit.getPopularity());
            updatedMovieCredit.setVoteAverage(movieCredit.getVoteAverage());
            updatedMovieCredit.setActor(movieCredit.getActor());
            updatedMovieCredit.setPersonDetails(personMap.get(movieCredit.getActor()));

            movieCredits.add(updatedMovieCredit);
        }
        movieDetails.setMovieCredits(movieCredits);

        return movieDetails;
    }

    private String getCrewMember(Credits credits, String jobTitle) {
        for (CrewMember crewMember : credits.getCrew()) {
            if (crewMember.getJob().equals(jobTitle)) {
                return crewMember.getName();
            }
        }
        return "Not Available";
    }

    private String getMainActors(Credits credits) {
        List<String> actors = credits.getCast().stream().limit(1000).map(CrewMember::getName).collect(Collectors.toList());
        return String.join(", ", actors);
    }

    private String getTopWriters(Credits credits) {
        List<String> writers = credits.getCrew().stream()
                .filter(crewMember -> crewMember.getDepartment().equals("Writing"))
                .limit(5)
                .map(CrewMember::getName)
                .collect(Collectors.toList());
        return String.join(", ", writers);
    }

    private String getImdbId(String title) {
        ImdbIMDB imdb = new ImdbIMDB();
        Movie movie = imdb.getMovie(title);
        return movie != null ? movie.getId().substring(2) : "Not Available";
    }

    private String getWikiUrl(String title) {
        try {
            String wikiUrl = "https://en.wikipedia.org/w/api.php?" +
                    "action=query&list=search&srsearch=" + title.replace(' ', '%20') +
                    "&format=json";
            String result = asyncHttpClient.get(wikiUrl).execute().body().asString(UTF_8);
            JSONObject json = jsonParser.parse(result).asObject();
            JSONArray searchResults = json.getJSONArray("query").getJSONObject("search");
            String pageTitle = searchResults.getJSONObject(0).getString("title");
            return "https://en.wikipedia.org/wiki/" + pageTitle.replace(' ', '_');
        } catch (Exception e) {
            return "Wikipedia page not found";
        }
    }

    private static final String UTF_8 = "UTF-8";
    private static final Set<Integer> featureFilmGenreIds = Set.of(
            12, 14, 16, 18, 27, 28, 35, 36, 37, 53, 80,
            878, 9648, 10402, 10749, 10751, 10752
    );
    private static final int minVoteCount = 50;

    private final Map<String, MovieDetails> movieCache = new ConcurrentHashMap<>();
    private final Map<String, PersonDetails> personCache = new ConcurrentHashMap<>();
}