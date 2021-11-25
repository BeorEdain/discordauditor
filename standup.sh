#! /bin/sh
cd Discord_Auditor/
docker build -t discord-auditor-bot:production .
docker-compose up -d