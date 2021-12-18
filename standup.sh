#! /bin/sh
docker build -t discord-auditor-bot:production .
docker-compose -p discord-auditor up -d