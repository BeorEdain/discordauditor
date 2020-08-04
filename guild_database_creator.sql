CREATE DATABASE guildList;

USE guildList;

CREATE TABLE Guilds (
	guildID bigint NOT NULL,
	guildName varchar(255),
	guildOwner bigint NOT NULL
	PRIMARY KEY (guildID)
);