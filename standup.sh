#! /bin/sh
docker build --no-cache --tag discord-auditor-bot:production .
docker-compose --project-name discord-auditor up --detach