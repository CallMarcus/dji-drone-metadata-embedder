FROM python:3.11-slim

# Install ffmpeg and exiftool
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg exiftool \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

ENTRYPOINT ["dji-embed"]
CMD ["--help"]
