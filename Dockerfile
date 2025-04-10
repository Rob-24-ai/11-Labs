FROM python:3.9-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install libmagic for python-magic
RUN apt-get update && apt-get install -y libmagic1 && apt-get clean

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE 5002

# Command to run the application
CMD ["python", "app.py"]
