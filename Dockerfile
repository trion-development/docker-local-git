FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /git-repos /app
WORKDIR /app
COPY server.py .

EXPOSE 8080

CMD ["python", "-u", "server.py"]