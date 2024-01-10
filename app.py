from flask import Flask, request, render_template, jsonify, session
import subprocess
import threading
import asyncio
import discord
import requests
import os
import yaml


# Updated import statements
from managers.config_manager import ConfigManager
from managers.data_manager import DataManager
from managers.radarr_manager import RadarrManager
from managers.openai_chat_manager import OpenAIChatManager

from managers.movie_data_builder import MovieDataBuilder

# Import DiscordBot from the bots directory if needed
# from bots.discord_bot import DiscordBot


app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.urandom(24)

config_manager = ConfigManager()
data_manager = DataManager(config_manager)
radarr_manager = RadarrManager(config_manager, data_manager)
openai_chat_manager = OpenAIChatManager(config_manager, data_manager)
# discord_bot = DiscordBot(config_manager, data_manager, radarr_manager)


##########################################################################################
# THIS IS KINDA JANK!!
# This is for building a database of movies/people in cache.json.
# It takes the movie, and looks at all the actors in it and their credits.
# It then gets all the movie details for all those credits from all the
# actors in the named movie. You have to let it finsih or it will break
# the json file and you will have to start over with a fresh one. The people
# one just does the opposite.

# Some have been ran and some have not, hard to say.
actors = [
    # "Meryl Streep",
    # "Denzel Washington",
    # "Amitabh Bachchan",
    # "Toshiro Mifune",
    # "Ingrid Bergman",
    # "Sidney Poitier",
    # "Al Pacino",
    # "Charlize Theron",
    # "Kang-ho Song",
    # "Cate Blanchett",
    # "Daniel Day-Lewis",
    # "Isabelle Huppert",
    # "Rami Malek",
    # "Viola Davis",
    # "Tony Leung Chiu-wai",
    # "Marion Cotillard",
    # "Joaquin Phoenix",
    # "Lupita Nyong'o",
    # "Javier Bardem",
    # "Gong Li",
    # "Steve Martin",
    # "Melissa McCarthy",
    # "Eddie Murphy",
    # "Kristen Wiig",
    # "Bill Murray",
    # "Tina Fey",
    # "Robin Williams",
    # "Amy Poehler",
    # "Jim Carrey",
    # "Whoopi Goldberg",
    # "Audrey Hepburn",
    # "Brad Pitt",
]

# These have all been ran
movies = [
    # "In the Mood for Love",
    # "Avengers: Endgame",
    # "Blade Runner",
    # "Inception",
    # "Rear Window",
    # "Schindler's List",
    # "Halloween",
    # "Forrest Gump",
    # "Bringing Up Baby",
    # "The Godfather",
    # "The Matrix",
    # "Pulp Fiction",
    # "Citizen Kane",
    # "Psycho",
    # "Lost in Translation",
    # "Metropolis",
    # "Solaris",
    # "Amélie",
    # "12 Angry Men",
    # "The Seventh Seal",
    # "Rashomon",
    # "Vertigo",
    # "A Clockwork Orange",
    # "Seven Samurai",
    # "La La Land",
    # "The Shawshank Redemption",
    # "Amadeus",
    # "Parasite",
    # "Oldboy",
    # "The Lives of Others",
    # "Pan's Labyrinth",
    # "Moonlight",
    # "Roma",
    # "A Separation",
    # "Whiplash",
    #  "Eternal Sunshine of the Spotless Mind",
    # "City of God",
    # "The Intouchables",
    # "Jojo Rabbit",
    # "Life Is Beautiful",
    # "Spirited Away",
    #  "Mad Max: Fury Road",
    # "Some Like It Hot",
    # "The Big Lebowski",
    # "Groundhog Day",
    #  "Monty Python and the Holy Grail",
    # "Superbad",
    # "The Grand Budapest Hotel",
    # "Casablanca",
]

movie_builder = MovieDataBuilder(data_manager)


async def call_build_data(actors, movies):
    # for actor in actors:
    # print("::::::::::::FINISHED BUILDING DATA FOR ALL ACTORS::::::::::::")
    for movie in movies:
        await movie_builder.build_data_for_movie(movie)
    print("::::::::::::FINISHED BUILDING DATA FOR ALL MOVIES::::::::::::")


# As long as this is commented out, it wil just run without the data building
# asyncio.run(call_build_data(actors, movies))

###########################################################################################


channels_data = []


def start_discord_bot_process():
    subprocess.Popen(["python", "bots/DiscordBot.py"])


def start_discord_client(token):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(get_channels(token))


async def get_channels(token):
    global channels_data
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        channels_data.clear()
        for guild in client.guilds:
            for channel in guild.text_channels:
                channels_data.append({"id": str(channel.id), "name": channel.name})
        await client.close()

    await client.login(token)
    await client.start(token)


@app.route("/server_status")
def server_status():
    return jsonify({"status": "ready"})


@app.route("/channels", methods=["GET"])
def channels_endpoint():
    token = request.args.get("token")
    if token:
        thread = threading.Thread(target=start_discord_client, args=(token,))
        thread.start()
        thread.join()
        return jsonify(channels_data)
    return jsonify({"error": "No token provided"})


@app.route("/load_config", methods=["GET"])
def load_config_endpoint():
    config_manager.load_config()
    return jsonify({"message": "Configuration reloaded on the server"})


@app.route("/fetch_root_folders")
def fetch_root_folders():
    radarr_url = request.args.get("radarr_url")
    radarr_api_key = request.args.get("radarr_api_key")

    if radarr_url and radarr_api_key:
        try:
            url = f"{radarr_url}/api/v3/rootfolder"
            headers = {"X-Api-Key": radarr_api_key}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return jsonify(response.json())
            else:
                return jsonify({"error": f"HTTP {response.status_code}"})
        except Exception as e:
            return jsonify({"error": str(e)})
    return jsonify({"error": "Radarr URL or API key not provided"})


@app.route("/person/<int:person_id>/movie_credits")
def person_movie_credits(person_id):
    try:
        credits = data_manager.get_person_movie_credits(person_id)
        return jsonify(credits), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        for key in [
            "tmdb_api_key",
            "radarr_url",
            "radarr_api_key",
            "openai_api_key",
            "discord_token",
            "radarr_quality",
            "selected_model",
            "discord_channel",
        ]:
            form_value = request.form.get(key)
            if form_value:
                config_manager.config[key] = form_value

        discord_channel_id = request.form.get("discord_channel")
        if discord_channel_id:
            config_manager.config["discord_channel_id"] = discord_channel_id

        radarr_root_folder = request.form.get("radarr_root_folder")
        if radarr_root_folder:
            config_manager.config["radarr_root_folder"] = radarr_root_folder

        selected_model = config_manager.get_config_value("selected_model")
        if selected_model == "gpt-3.5-turbo-1106":
            config_manager.config["max_chars"] = 65540
        elif selected_model == "gpt-4-1106-preview":
            config_manager.config["max_chars"] = 512000

        start_discord_bot = request.form.get("start_discord_bot_on_launch") == "on"
        config_manager.config["start_discord_bot_on_launch"] = start_discord_bot

        with open(config_manager.config_path, "w") as file:
            yaml.dump(config_manager.config, file)

        data_manager.update_tmdb_api_key()
        radarr_manager.radarr = radarr_manager.initialize_radarr()
        openai_chat_manager.initialize_openai_client()

        if config_manager.get_config_value("start_discord_bot_on_launch"):
            start_discord_bot_process()
        #    bot = DiscordBot()
        #    bot.start_bot()

    root_folders = []
    return render_template(
        "index.html", config=config_manager.config, root_folders=root_folders
    )


@app.route("/movie_details/<int:tmdb_id>")
def movie_details(tmdb_id):
    try:
        movie_details = data_manager.get_movie_card_details(tmdb_id)
        return jsonify(movie_details)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/send_message", methods=["POST"])
def send_message():
    message = request.json["message"]

    if "conversation_history" not in session:
        session["conversation_history"] = []

    conversation_history = session["conversation_history"]
    response = openai_chat_manager.get_openai_response(conversation_history, message)
    session["conversation_history"] = conversation_history
    return jsonify({"response": response})


@app.route("/person_details/<name>")
def person_details(name):
    details = data_manager.get_person_details(name)
    return jsonify(details)


@app.route("/add_movie_to_radarr/<int:tmdb_id>", methods=["GET"])
def add_movie_to_radarr(tmdb_id):
    quality_profile_id = config_manager.get_config_value("radarr_quality")
    root_folder = config_manager.get_config_value("radarr_root_folder")

    response_dict = radarr_manager.add_movie(tmdb_id, quality_profile_id, root_folder)
    return jsonify(response_dict)


@app.route("/movie_card_details/<int:tmdb_id>")
def movie_card_details(tmdb_id):
    details = data_manager.get_movie_card_details(tmdb_id)
    return jsonify(details)
