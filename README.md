# Chatarr

Chatarr is an OpenAI based chatbot that integrates with Radarr. Whenever the chatbot mentions a movie, you simply click it to add it to Radarr and download it. There are popovers for movies and people.

Person popovers have birth/death day, movie credits and a biography. From the person popover, you can click any of the movie credits to ask the chatbot about that particular movie. There are also buttons to ask the chat bot about the person, go to their IMDb and go to their wiki.

Movie popovers come up when you hover over a movie and they contain information about the movie from TMDb. It has the firector, the director of photography, the writers, the actors/stars, the TMDb rating, the release date, and a description of the movie as well as a poster. You can click any of the stars to open their person popover. There are also Add to Radarr, Ask Chatarr, IMDb and Wiki buttons in the popover.

There is a discord bot included, but it isn't perfect. Right now you can start it from the config by saving your discord token for your bot and picking a channel. To stop the discord bot you have to stop the whole thing, or restart it. It works through reactions in disord. Any time it mentions a movie, it adds a emoji that corresponds with the reaction in it's message. You can click the reaction at the bottom of the message to add the movie to radarr.

# Installation

##Docker

The easiest way is to just use docker:

```bash
docker pull staythepath/chatarr:latest
```

It should just start up on port 1138.
