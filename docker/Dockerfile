FROM python:3.10 as requirements-stage

WORKDIR /tmp

RUN pip install -U pip setuptools wheel
RUN pip install pdm 

COPY ./pyproject.toml ./pdm.lock* /tmp/

RUN pdm export -f requirements --output requirements.txt --without-hashes -G adapters -G nonebot -G impl

FROM python:3.10-slim

WORKDIR /app

ENV TZ Asia/Shanghai
ENV PYTHONPATH=/app

COPY --from=requirements-stage /tmp/requirements.txt /app/requirements.txt
RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get install -y --no-install-recommends git \
    && pip install --no-cache-dir --upgrade -r requirements.txt \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/* \
    && rm /app/requirements.txt

COPY ./docker/bot.py ./docker/.env /app/
COPY ./nonebot_plugin_all4one/ /app/nonebot_plugin_all4one/

CMD ["python", "bot.py"]
