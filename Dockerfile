# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Check if config.yaml exists, if not create it with default values
RUN if [ ! -f config.yaml ]; then \
    echo "tmdb_api_key: ''\nradarr_url: ''\nradarr_api_key: ''\nopenai_api_key: ''\ndiscord_token: ''\nradarr_quality: ''\nselected_model: ''\nmax_chars: 65540\ndiscord_channel: ''\nradarr_root_folder: ''" > config.yaml; \
    fi

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 1138 available to the world outside this container
EXPOSE 1138

# Define environment variable
ENV FLASK_APP=config_ui.py

# Run app.py when the container launches
CMD ["gunicorn", "--bind", "0.0.0.0:1138", "app:app"]
