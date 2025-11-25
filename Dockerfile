# Use Python 3.11 slim image for a balance of size and compatibility
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHON_IN_DOCKER=true \
    CHROME_BINARY_PATH=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    TZ=Asia/Shanghai

# Install system dependencies
# chromium: The browser
# chromium-driver: The driver (optional, but good to have system libs)
# fonts-wqy-zenhei: Chinese fonts for proper rendering
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create a volume for data persistence (database)
VOLUME /data

# Run the application
CMD ["python", "startup.py"]
