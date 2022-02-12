GRANT ALL ON *.* TO 'beoredain'@'%';
FLUSH PRIVILEGES;
USE guildList;
CREATE TABLE Guilds (
	guildID bigint NOT NULL,
	guildName varchar(255) NOT NULL,
	guildOwner bigint NOT NULL,
	enrolledOn datetime NOT NULL DEFAULT '1970-01-01 00:00:01.000000',
	currentlyEnrolled boolean NOT NULL DEFAULT '1',
	oustedOn datetime,
	PRIMARY KEY (guildID)
);