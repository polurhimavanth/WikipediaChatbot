# # Use an official Python image as a base
# FROM python:3.10-slim

# # Set the working directory inside the container
# WORKDIR /app

# # Install dependencies
# COPY requirements.txt ./
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy the rest of the application
# COPY . .

# # Expose a port (optional, adjust as needed for your app)
# EXPOSE 8000

# # Set the default command to run your script
# CMD ["python", "main.py"]









# # Use a base image with Python
# FROM python:3.8-slim

# # Set the working directory inside the container
# WORKDIR /app

# # Copy the application code into the container
# COPY . /app

# # Install dependencies (assuming requirements.txt exists)
# RUN pip install --no-cache-dir -r requirements.txt

# # Set the environment variable for Flask or any other environment variables if needed
# ENV FLASK_APP=main.py

# # Set the command to run the application
# CMD ["python", "main.py"]



# Use an official Python image as a base
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application into the container
COPY . .

# Set the environment variable for Flask
ENV FLASK_APP=main.py

# Expose port 8125 for the Flask app
EXPOSE 8125

# Command to run the application with Flask
CMD ["flask", "run", "--host=0.0.0.0", "--port=8125"]
