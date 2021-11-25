#! /bin/sh
docker kill discord-auditor-bot
docker kill discord-auditor-database
docker rm discord-auditor-bot
docker rm discord-auditor-database
docker rmi discord-auditor-bot:production
docker volume rm discord_auditor_attachment-volume
docker volume rm discord_auditor_database-volume