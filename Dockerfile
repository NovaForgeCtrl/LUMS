FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dedicated unprivileged runtime user.
RUN groupadd --system --gid 10001 lums \
    && useradd --system \
        --uid 10001 \
        --gid 10001 \
        --home-dir /nonexistent \
        --no-create-home \
        --shell /usr/sbin/nologin \
        lums

WORKDIR /app

COPY server/requirements.txt /app/server/requirements.txt

RUN pip install --no-cache-dir \
    -r /app/server/requirements.txt

COPY server /app/server
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

RUN chmod 755 /app/docker-entrypoint.sh \
    && mkdir -p /var/lib/lums \
    && chown -R lums:lums /var/lib/lums

WORKDIR /app/server

EXPOSE 5000

USER lums

ENTRYPOINT ["/app/docker-entrypoint.sh"]
