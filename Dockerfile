# Use an official Python runtime as the base image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install dependencies from the 'functions' folder
RUN pip install --no-cache-dir -r /app/functions/requirements.txt

# Expose the port that Flask will run on (adjusted to 5000)
EXPOSE 5001

# Set environment variables for Flask
ENV FLASK_APP=functions/app.py   
ENV FLASK_RUN_HOST=0.0.0.0

# Run Flask app
CMD ["flask", "run", "--host=0.0.0.0", "--port=5001"]
