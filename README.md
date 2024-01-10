# Chatarr

**THIS COSTS MONEY!!!! IF YOU ARE USING IT A LOT ON GPT-4 IT MIGHT ADD UP!!!! CHECK YOUR USAGE TO KNOW WHAT YOU ARE SPENDING WHEN USING THIS!!! HOWEVER, IF YOU ARE USING GPT-3.5 IT'S RELATIVELY CHEAP!**

Chatarr is an OpenAI based chatbot that integrates with Radarr. Whenever the chatbot mentions a movie, you simply click it to add it to Radarr and download it. There are popovers for movies and people.

Person popovers have birth/death day, movie credits and a biography. From the person popover, you can click any of the movie credits to ask the chatbot about that particular movie. There are also buttons to ask the chat bot about the person, go to their IMDb and go to their wiki.

Movie popovers come up when you hover over a movie and they contain information about the movie from TMDb. It has the firector, the director of photography, the writers, the actors/stars, the TMDb rating, the release date, and a description of the movie as well as a poster. You can click any of the stars to open their person popover. There are also Add to Radarr, Ask Chatarr, IMDb and Wiki buttons in the popover.

There is a discord bot included, but it isn't perfect. Right now you can start it from the config by saving your discord token for your bot and picking a channel. To stop the discord bot you have to stop the whole thing, or restart it. It works through reactions in disord. Any time it mentions a movie, it adds a emoji that corresponds with the reaction in it's message. You can click the reaction at the bottom of the message to add the movie to radarr.

# Installation

### Docker

The easiest way is to just use docker:

```bash
docker pull staythepath/chatarr:latest
```

Pick a host port and run it. The container port needs to be 1138. I think the container port is done automatically, but I'm not sure because I'm dumb.

### Linux

Alternatively you can clone the repo:

```python
git clone https://github.com/staythepath/chatarr.git
```

then go to the folder:

```
cd chatarr
```

Install the requirements(I would start a new environment for this):

```
pip3 install -r requirements.txt
```

Then you should be able to start it with:

```
gunicorn --bind 0.0.0.0:1138 --timeout 60 app:app
```

### Unraid

I don't have this in the Community Applications yet, but I hope to get it there at some point. However, you can copy the chatarr.xml from the route of the repo directory to

```
/boot/config/plugins/dockerMan/templates-user/
```

Then you can simply go to your docker tab and you should have a chatarr template you can choose in the template dropdown at the very top and you should be able to just add it and be good to go.

### Setup

Click the config button in the top right.

#### OpenAI API Key:

**THIS COSTS MONEY!!!! IF YOU ARE USING IT A LOT ON GPT-4 IT MIGHT ADD UP!!!! CHECK YOUR USAGE TO KNOW WHAT YOU ARE SPENDING WHEN USING THIS!!!** Using gpt-3.5 seems perfectly sufficient to me and it's really cheap. I spent well under 5 dollars over a week of hammering the GPT-3.5 API constantly while I was developing this. Under regular use(whatever that is) it shouldn't cost too much as long as you stick to GPT-3.5. Sign up with OpenAI and grab an API key.

#### Radarr API Key, URL, Quality, Root folder:

If you're reading this, I'm sure you can figure this stuff out. You can find all this stuff is in Radarr itself. You do need to specify the exact quality you want. I have a quality profile called, "this" and I just put in "this" (no quotes) and it uses that profile when downloading.I have a quality Making the quality a dropdown is on the (long) list of feature I want to add. The root folder should auto populate, and I think most people won't need to change it from what it loads with, but you should definitely check to make sure you are using the right one. All this stuff is necessary to send the movie to radarr.

#### TMDb key:

Just go to https://www.themoviedb.org and sign up and grab an API key. This is where I grab all(well most) of the movie data from. There is a cache I'm working on to prevent having to make API calls for every popover here, but if you are even kind of into movies, you will run across stuff not in the cache. It's a work in progress.

#### Model:

You're just selecting which OpenAI model to use. As I've explained, GPT-3.5 feels sufficient to me in most cases and it's also faster, but GPT-4 definitely tends to give more in depth and accurate answers. If you feel the need to bump it to GPT-4, just watch your usage.

## Contributing

PLEASE HELP ME!. I'm very new to all this. I'm open to criticism, new ideas, contributions of any kind or any feedback you can give me AT ALL. I'm really just trying to learn and to build something that people actually use so any input you can give me is greatly appreciated.

## Other stuff

If I'm being perfectly honest I don't really know what I'm doing and this is the first thing I've ever really posted anywhere publicly. ChatGPT and Co-pilot did write tons of the code, and although I understand almost all of it, I still feel like I should be a bit embarrassed by what is in here. I'm sure I'm doing some stuff totally wrong and I'd love if someone pointed that stuff out. I don't know if I just use this and feel like it's useful because I made it, or if other people will actually get some use out of it, but I would love if they did, so that's what I'm working towards. I won't be remotely surprised if no one uses this at all, but I hope they do.

## Plans

There is a lot of stuff I want to add, but I only have so much time, so I'll add some of this stuff as best I can. This isn't a hard and fast order I intend to add stuff, but here is the stuff I want to add.

    * Data builder for crew. Writers, Directors, DoP etc.
        * Given director, writer, producer etc, ask openai for 20 similar or related directors along with and gather their info and all the info for all their movies and actors in those movies
    * Fix popovers not working when waiting on OpenAI response
    * The second it gets the movie titles, and actors, it need to start the api calls for their data IF it doesnt have it already.
    * Download tracking.
        * Sidebar with current downloads(does this mean downloader integration as well or can this be done through radarr?)
        The message that indicates it has been "Added to Radarr" Changes to "Downloading *Movie Title* *Pause/Resume button* *Delete* *Progress Bar*" when downloading, then to "Download completed" when it's done
    * Make the mobile site less sucky
    * Add option to turn off click movie to add
    * Add option to turn off popovers
    * Add option to add to radarr but not download
    * MAYBE add option to edit system prompt. If people mess with it it will probably break functionality
    * Adjust system prompt
    * Add stop button when waiting for the OpenAI response to cancel the response
    * Add option to edit how much chat history is maintained, which will help lower costs if needed
    * Infinitely nesting popovers instead of the person popover credits just asking Cheddar about the person. This seems like it could be problematic and difficult
    * Add a sidebar on the right that has movie posters that are related to the movies or actors being discussed Adjust with each message. Clicking the poster gives the movie popover
    * Fix some people(I think it's non-actors specically) not having the right credits. I feel like John Williams has contributed to more than 4 movies
    * Chat message indicating that API keys etc have not been set/set properly. Indicate which one is wrong.
    * Sonnar support
