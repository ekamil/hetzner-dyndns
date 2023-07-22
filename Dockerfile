FROM python:3-alpine

RUN pip install pipenv

COPY ./Pipfile /Pipfile
COPY ./Pipfile.lock /Pipfile.lock

RUN pipenv install --system --deploy

COPY ./update-hetzner-domain.py /update-hetzner-domain.py
COPY ./docker-entrypoint.sh /docker-entrypoint.sh

ENV HETZNER_DNS_API_KEY=CHANGE_ME
ENV DYNAMIC_DOMAIN=CHANGE_ME

ENTRYPOINT ["/docker-entrypoint.sh"]
