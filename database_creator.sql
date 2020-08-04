CREATE TABLE Channels (
	channelID bigint NOT NULL,
	channelName varchar(255),
	isNSFW boolean,
	isNews boolean,
	categoryID bigint,
	PRIMARY KEY (channelID)
);

CREATE TABLE Members (
	memberID bigint NOT NULL,
	memberName varchar(255) NOT NULL,
	discriminator bigint NOT NULL,
	isBot boolean,
	nickname varchar(255),
	PRIMARY KEY (memberID)
);

CREATE TABLE Messages (
	ID int NOT NULL AUTO_INCREMENT,
	messageID bigint NOT NULL,
	channelID bigint NOT NULL,
	authorID bigint NOT NULL,
	dateCreated timestamp NOT NULL,
	isEdited boolean NOT NULL DEFAULT 0,
	dateEdited timestamp,
	isDeleted boolean NOT NULL DEFAULT 0,
	dateDeleted timestamp,
	message varchar(10000),
	hasAttachment boolean NOT NULL DEFAULT 0,
	attachmentID bigint,
	filename varchar(255),
	url varchar(255),
	PRIMARY KEY (ID),
	FOREIGN KEY (channelID) REFERENCES Channels(channelID),
	FOREIGN KEY (authorID) REFERENCES Members(memberID)
);