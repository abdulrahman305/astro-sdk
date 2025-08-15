FROM postgres:16.8-bookworm
RUN apt-get update && apt-get -y install git
ENV POSTGRES_DB pagila
ENV POSTGRES_USER postgres
ENV POSTGRES_PASSWORD postgres

COPY *.sh /docker-entrypoint-initdb.d/
EXPOSE 5432

CMD ["postgres"]
