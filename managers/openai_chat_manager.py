import openai
import re
from openai import OpenAI
import time


class OpenAIChatManager:
    def __init__(self, config_manager, tmdb_manager):
        self.config_manager = config_manager
        self.tmdb_manager = tmdb_manager
        self.initialize_openai_client()

    def initialize_openai_client(self):
        self.openai_api_key = self.config_manager.get_config_value("openai_api_key")
        self.max_chars = self.config_manager.get_config_value("max_chars")
        self.selected_model = self.config_manager.get_config_value("selected_model")
        self.client = OpenAI(api_key=self.openai_api_key)

    def trim_conversation_history(self, conversation_history, new_message):
        conversation_history.append(new_message)
        total_chars = sum(len(msg["content"]) for msg in conversation_history)
        while total_chars > self.max_chars and len(conversation_history) > 1:
            removed_message = conversation_history.pop(0)
            total_chars -= len(removed_message["content"])
        return conversation_history

    def get_openai_response(self, conversation_history, message):
        # Prepare new message and conversation history
        new_message = {"role": "user", "content": message}
        conversation_history = self.trim_conversation_history(
            conversation_history, new_message
        )

        messages = [
            {
                "role": "system",
                "content": "Use asterisks (*) to surround movie titles and include the year in parentheses after the title, like *Movie Title* (Year) (e.g., *Jurassic Park* (1994)). Never under any circumstances use double astericks (**) for anything. Always put exactly one asteriks in the fron of the title and one at the end. No more no less.For actors, directors, or any person with an IMDb presence, wrap their names in '#' symbols like this: #Actor's Name# or #Director's Name#. Avoid using asterisks or # for anything other than movie titles. Any person you mention who works or has worked in movies needs to get their name wrapped in # like this, #Bradd Pitt# . Any time an actor, director, writer, cinematographer or ANY person that works in the movie business is mentioned in your response, you need to wrap their name in #'s like this, #Alfred Hitchcock# and you absolutely must wrap it like that any time you mention a name of someone who works or has worked in the movie business. Make sure movie titles match those on the TMDB website exactly, including capitalization, spelling, punctuation, and spacing. Use a dash (-) for lists instead of numbering and whenever you make a list, be sure to put each movie on it's own new line. Be conversational, engage with user preferences, and share interesting and fun movie facts or trivia as much as possible. Only create lists when relevant or requested. Your primary focus is movies, but you can continue conversations if the user diverges from the topic. If a person asks you to list movies, just list them instead of trying to ask what kind of movies.",
            }
        ] + conversation_history

        print("Here is the message: ", messages)

        # Generate response from OpenAI
        response = self.client.chat.completions.create(
            model=self.selected_model, messages=messages, temperature=0
        )
        response_content = (
            response.choices[0].message.content.strip()
            if response.choices
            else "No response received."
        )

        print("OpenAI response: ", response_content)

        # Add bot's response to conversation history
        bot_response = {"role": "assistant", "content": response_content}
        conversation_history = self.trim_conversation_history(
            conversation_history, bot_response
        )

        # Process movie titles
        movie_titles_map = self.check_for_movie_title_in_string(response_content)
        for title, tmdb_id in movie_titles_map.items():
            response_content = response_content.replace(
                f"*{title}*",
                f"<span class='movie-link' data-toggle='popover' data-tmdb-id='{tmdb_id}' data-title='{title}'>{title}</span>",
            )
        return response_content

    def check_for_movie_title_in_string(self, text):
        movie_titles_map = {}
        phrases_in_stars = re.findall(r"\*\"?([^*]+)\"?\*(?: \(\d{4}\))?", text)

        for phrase in phrases_in_stars:
            # Use the tmdb_manager's search_movie method
            results = self.tmdb_manager.search_movie(phrase)
            print(f"\nSearch phrase: '{phrase}'")
            print("Results:")

            # Introduce a delay to prevent hitting API rate limits
            # time.sleep(0.1)

            for idx, result in enumerate(results):
                if isinstance(result, dict) and "title" in result and "id" in result:
                    print(f"  Result {idx + 1}: {result}")
                    tmdb_id = result["id"]
                elif hasattr(result, "title") and hasattr(result, "id"):
                    print(
                        f"  Result {idx + 1}: Title - {result.title}, ID - {result.id}"
                    )
                    tmdb_id = result.id
                else:
                    print(f"  Result {idx + 1}: Invalid format")
                    continue

                if tmdb_id:
                    movie_titles_map[phrase] = tmdb_id
                    break  # Stop after finding the first valid result

        return movie_titles_map
