FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Copy and install Python dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -U pip && \
    pip3 install --no-cache-dir -U -r requirements.txt

# Copy all bot files
COPY . .

# HF Spaces requires port 7860 to be exposed
EXPOSE 7860

# Start the bot directly
CMD ["python3", "bot.py"]
