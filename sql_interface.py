import os
import platform
from datetime import datetime

import discord
from mysql.connector import (
    IntegrityError, MySQLConnection, ProgrammingError, connect)

time_format = "%Y-%m-%d %H:%M:%S"

attach_path_linux = "~/discordauditor/"
attach_path_windows = "discordauditor/"

def get_credentials(spec_database=None) -> MySQLConnection:
    """
    A helper function used to get the credentials for the server, simplifying
    the process.
    """
    # Try to get the credentials for the server.
    credentials = []
    try:
        with open("sensitive/database_credentials", 'rt') as key:
            for item in key:
                credentials.append(str(item).strip())
    
    # If the file isn't there, exit.
    except FileNotFoundError:
        print("database_credentials does not exist.")
        exit()

    # Try the connection.
    try:
        if not spec_database:
            mydb = connect(
                host=credentials[0],
                user=credentials[1],
                password=credentials[2])
        else:
            mydb = connect(
                host=credentials[0],
                user=credentials[1],
                password=credentials[2],
                database="server"+str(spec_database))
        
        return mydb

    # If the connection cannot be established due to input error, log and quit.
    except ProgrammingError:
        print("There was an error with the credentials.")
        exit()

async def new_message(message: discord.Message):
    """Called when a new message is added to an audited server."""
    # Get the initial connection to the database
    connection = get_credentials(message.guild.id)

    # Select only the members who have a matching memberID (Hint, there's only
    # ever going to be one as it's the primary key of the member table).
    sql = "SELECT * FROM Members WHERE memberID = %s"
    val = (message.author.id,)

    # Create the cursor and execute the command.
    cursor = connection.cursor()
    cursor.execute(sql, val)

    # Get the results of the previous command.
    records = cursor.fetchall()

    # If there is no results, then the member doesn't exist in the table yet, so
    # they need to be added.
    if len(records) == 0:
        # Build the SQL command.
        sql = ("INSERT INTO Members (memberID,memberName,discriminator,isBot) "+
               "VALUES (%s,%s,%s,%s)")
        
        # Add the values to a tuple.
        val = (message.author.id,message.author.name,
                    message.author.discriminator,message.author.bot)
        
        # Execute the command.
        cursor.execute(sql,val)
        connection.commit()

    # Create the command to add the message to the Messages table.
    if message.attachments:
        for attachment in message.attachments:
            sql = ("INSERT INTO Messages (messageID, channelID, authorID,"+
                "dateCreated, message, hasAttachment, attachmentID, filename,"+
                "url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)")

            # Add the values of the message as a tuple.
            val = (message.id, message.channel.id, message.author.id,
                    message.created_at, message.content, True, attachment.id,
                    attachment.filename, attachment.url)

            directory = ""
            server = f"server{message.guild.id}/"

            if platform.system() == "Linux":
                if not os.path.isdir(f"{attach_path_linux}{message.guild.id}/"):
                    os.mkdir(attach_path_linux + server)
                    directory = attach_path_linux + server

            elif platform.system() == "Windows":
                if not os.path.isdir(f"{attach_path_windows}{message.guild.id}/"):
                    try:
                        os.mkdir(attach_path_windows)
                    except FileExistsError:
                        pass
                    try:
                        os.mkdir(attach_path_windows + server)
                    except FileExistsError:
                        pass

                    directory = attach_path_windows + server
            
            directory = (directory + str(message.attachments[0].id)+
                            message.attachments[0].filename)

            if not os.path.isfile(directory):
                await discord.Attachment.save(message.attachments[0],directory)

    else:
        sql = ("INSERT INTO Messages (messageID, channelID, authorID,"+
               "dateCreated, message) VALUES (%s,%s,%s,%s,%s)")
        val = (message.id, message.channel.id, message.author.id,
               message.created_at, message.content)

    # Set up the cursor.
    cursor = connection.cursor()

    # Execute the command and commit it to the database.
    cursor.execute(sql, val)
    connection.commit()
    connection.close()

def edited_message(message: discord.Message):
    """Called when a message is edited in an audited server."""
    # Get the initial connection to the database.
    connection = get_credentials(message.guild.id)

    current_time = datetime.utcnow().strftime(time_format)

    # Set the prepared statement to update the appropriate values.
    sql = "UPDATE Messages SET isEdited=%s, dateEdited=%s WHERE messageID=%s"
    val = (True,current_time,message.id)

    # Set up the cursor, execute the command, then close the connection.
    cursor = connection.cursor()
    cursor.execute(sql,val)
    connection.commit()
    connection.close()

def deleted_message(message: discord.Message):
    """Called when a message is deleted from an audited server."""
    # Get the initial connection to the database.
    connection = get_credentials(message.guild.id)

    # Get the current UTC time to record when the message was deleted.
    current_time = datetime.utcnow().strftime(time_format)

    # Set up the prepared statement set the message as deleted and by whom.
    sql = "UPDATE Messages SET isDeleted=%s, dateDeleted=%s WHERE messageID=%s"
    val = (True,current_time,message.id)

    cursor = connection.cursor()
    cursor.execute(sql,val)
    connection.commit()
    connection.close()

def new_channel(channel: discord.TextChannel):
    """Called when a new channel is added to an audited server."""
    # Get the initial connection to the database.
    connection = get_credentials(channel.guild.id)

    # Set up the prepared statement to insert the new channel in to the table.
    sql = ("INSERT INTO Channels (channelID, channelName, isNSFW, isNews,"+
           "categoryID) VALUES (%s,%s,%s,%s,%s)")
    val = (channel.id, channel.name, channel.is_nsfw(), channel.is_news(),
           channel.category_id)

    # Set up the cursor, execute the command, and commit it to the databse.
    cursor = connection.cursor()
    cursor.execute(sql,val)
    connection.commit()
    cursor.close()

async def update_check(client:discord.Client):
    """
    Called once the bot is ready. Checks the currently enrolled guilds and 
    channels against the guilds and channels that are currently registered in
    the database, adding any new entries that were added since the bot was last
    run. 
    """
    # Get the guilds from the client.
    guilds = client.guilds

    # Get the credentials for the server and database from the file.
    mydb = get_credentials()

    # BEGIN GUILD CHECK ########################################################

    # Instantiate a list for the guilds that the bot is currently in.
    guild_list = []

    # Go through each guild and grab the ID for it to reference later.
    for guild in guilds:
        guild_list.append(guild.id)

    # Instantiate the cursor and execute the above command.
    cursor = mydb.cursor()
    cursor.execute("USE guildList")
    cursor.execute("SELECT guildID FROM Guilds")

    # Record the response from the server.
    records = cursor.fetchall()

    # Go through each record to ensure that all of the currently enrolled guilds
    # are part of the database.
    for row in records:
        # The need to call row at index 0 is a result of it returning a list of
        # tuples.
        if row[0] in guild_list:
            guild_list.remove(row[0])

    # If there are any left in the list of enrolled guilds.
    if len(guild_list) > 0:
        # Build the prepared statement to insert the values for the guild.
        sql = ("INSERT INTO Guilds (guildID, guildName, guildOwner) VALUES"+
               "(%s,%s, %s)")

        # Instantiate an empty list for the values.
        vals = []

        # Go through each guild in the guild_list.
        for guild in guild_list:
            # Use the guild ID to get the information about the specific guild.
            specific_guild = client.get_guild(guild)

            # Add the guild ID and guild name to the second part of the prepared
            # statement as a tuple.
            vals.append((specific_guild.id, specific_guild.name,
                         specific_guild.owner.id))

        # Add each of the tuples to the database.
        for value in vals:
            cursor.execute(sql, value)
            mydb.commit()

    # END GUILD CHECK ##########################################################
    # BEGIN CHANNEL CHECK ######################################################
    cursor.execute("SELECT guildID FROM Guilds")

    guilds = cursor.fetchall()

    # Instantiate a list for the channels that the bot can access.
    channel_list = []

    # Go through each channel in each guild and grab the ID for reference later.
    for guild in guilds:
        database = f"server{str(guild[0])}"
        try:
            cursor.execute(f"USE {database}")
        except ProgrammingError:
            create_new_guild_database(guild[0], mydb, cursor)

        for channel in client.get_guild(guild[0]).channels:
            # Only grab the IDs of the text channels as the bot has no use in a
            # voice channel for example and category channels don't have text in
            # them.
            if type(channel) == discord.channel.TextChannel:
                channel_list.append(channel.id)

        # Get all of the chennel IDs from the Channels table.
        sql = "SELECT channelID FROM Channels"

        # Instantiate the cursor and execute the above command.
        cursor.execute(sql)
        records = cursor.fetchall()

        # Go through each record to ensure that all of the currently enrolled
        # channels are part of the database.
        for row in records:
            if row[0] in channel_list:
                channel_list.remove(row[0])

        # If there are any left in the list of enrolled channels.
        if len(channel_list) > 0:
            # Build the prepared statement to insert the values for the
            # channels.
            sql = ("INSERT INTO Channels (channelID, channelName, isNSFW,"+
                   "isNews, categoryID) VALUES (%s,%s,%s,%s,%s)")
            
            # Instantiate an empty list for the values.
            vals = []

            # Go through each channel in the channel_list
            for channel in channel_list:
                # Use the channel ID to get the information about the specific
                # channel.
                specific_channel = client.get_channel(channel)

                # Add the channel ID, name, whether it's NSFW, whether it's
                # news, the category ID (if there is one), and the guild ID to
                # the second part of the prepared statement as a tuple.
                vals.append((specific_channel.id, specific_channel.name,
                            specific_channel.is_nsfw(),
                            specific_channel.is_news(),
                            specific_channel.category_id))
            
            # Add each of the tuples to the database.
            cursor.executemany(sql, vals)
            mydb.commit()
            channel_list.clear()

    # END CHANNEL CHECK ########################################################
    # BEGIN MEMBER CHECK #######################################################
    # Go through each guild.
    for guild in client.guilds:
        # Instantiate a list for the member IDs.
        members_id = []
        # Get the member ID of each member within the specific guild.
        for member in guild.members:
            members_id.append(member.id)
        
        # Specify which database will be used.
        cursor.execute(f"USE server{guild.id}")
        
        # Execute the command to get all of the member IDs from that database.
        cursor.execute("SELECT memberID FROM Members")
        records = cursor.fetchall()

        # Go through each record returned and remove it from the ID list if it
        # exists.
        for row in records:
            if row[0] in members_id:
                members_id.remove(row[0])

        # Instantiate a list that will hold the actual members that are new.
        members = []

        # Go through each one and get the member information.
        for member in members_id:
            spec_member = guild.get_member(member)
            members.append((spec_member.id,spec_member.name,
                            spec_member.discriminator,spec_member.bot))

        # If there are members to add to the database, add them.
        if len(members) > 0:
            sql = ("INSERT INTO Members (memberID,memberName,discriminator,"+
                   "isBot) VALUES (%s,%s,%s,%s)")
            cursor.executemany(sql,members)
            mydb.commit()
    
    # END MEMBER CHECK #########################################################
    # BEGIN MESSAGE CHECK ######################################################
    # Instantiate a list for the raw messages.
    raw_messages = []
    # Go through each guild.
    for guild in client.guilds:
        # Specify which database to use.
        cursor.execute(f"USE server{guild.id}")
        
        # Go through each channel
        for channel in guild.channels:
            # Only worry about text channels.
            if type(channel) == discord.channel.TextChannel:
                raw_messages = (raw_messages +
                               await channel.history(limit=None).flatten())

        # Get a list of messages that are already in the server.
        cursor.execute("SELECT messageID FROM Messages")
        records = cursor.fetchall()

        # Convert tuple'd records from SQL to simple list.
        message_ID_list = []
        for row in records:
            message_ID_list.append(row[0])

        # Use that list to remove any messages that are already in the server
        # from the raw message list.
        for mess in raw_messages:
            if mess.id in message_ID_list:
                raw_messages.remove(mess)

        # Instantiate two lists, one for messages with attachments and one for
        # messages without.
        to_upload_no_attach = []
        to_upload_attach = []

        # If there are messages to add.
        if len(raw_messages) > 0:
            for message in raw_messages:
                # If the message has one or more attachments.
                if message.attachments:
                    for attachment in message.attachments:
                        to_upload_attach.append((message.id, message.channel.id,
                                message.author.id, message.created_at,
                                message.content, True, attachment.id,
                                attachment.filename, attachment.url))
                        
                        directory = ""
                        server = f"server{guild.id}/"

                        if platform.system() == "Linux":
                            if not os.path.isdir(f"{attach_path_linux}"+
                                                 f"{guild.id}/"):
                                try:
                                    os.mkdir(attach_path_linux)
                                except FileExistsError:
                                    pass
                                try:
                                    os.mkdir(attach_path_linux + server)
                                except:
                                    pass
                                
                                directory = attach_path_linux + server

                        elif platform.system() == "Windows":
                            if not os.path.isdir(f"{attach_path_windows}"+
                                                 f"{guild.id}/"):
                                try:
                                    os.mkdir(attach_path_windows)
                                except FileExistsError:
                                    pass
                                try:
                                    os.mkdir(attach_path_windows + server)
                                except FileExistsError:
                                    pass

                                directory = attach_path_windows + server
                        
                        directory = (directory + str(message.attachments[0].id)+
                                     message.attachments[0].filename)

                        if not os.path.isfile(directory):
                            await discord.Attachment.save(message.attachments[0],
                                                        directory)
                
                # If the message has no attachments.
                else:
                    to_upload_no_attach.append((message.id, message.channel.id,
                            message.author.id, message.created_at,
                            message.content))

        # If there are attachment messages to add to the database.
        if len(to_upload_attach) > 0:
            sql = ("INSERT INTO Messages (messageID, channelID, authorID,"+
                   "dateCreated, message, hasAttachment, attachmentID,"+
                   "filename, url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)")
            
            cursor.executemany(sql, to_upload_attach)
            mydb.commit()

        # If there are non-attachment messages to add to the database.
        if len(to_upload_no_attach) > 0:
            sql = ("INSERT INTO Messages (messageID, channelID, authorID,"+
                   "dateCreated, message) VALUES (%s,%s,%s,%s,%s)")
            
            cursor.executemany(sql, to_upload_no_attach)
            mydb.commit()
        raw_messages.clear()

    mydb.close()

def create_new_guild_database(guild, mydb, cursor):
    """
    Creates a database and populates it with the required tables to function.
    """
    sql = f"CREATE DATABASE server{guild}"
    
    cursor.execute(sql)
    mydb.commit()

    cursor.execute(f"USE server{guild}")
    mydb.commit()

    sql = """CREATE TABLE Channels (
            channelID bigint NOT NULL,
            channelName varchar(255),
            isNSFW boolean,
            isNews boolean,
            categoryID bigint,
            isDeleted boolean,
            PRIMARY KEY (channelID)
        );

        CREATE TABLE Members (
            memberID bigint NOT NULL,
            memberName varchar(255) NOT NULL,
            discriminator bigint NOT NULL,
            isBot boolean,
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
        );"""

    cursor = mydb.cursor()

    # Enables the execute() command to go through each of the CREATE commands.
    for result in cursor.execute(sql, multi=True):
        result

def guild_join(guild: discord.Guild):
    """Called when a new guild is added."""
    mydb = get_credentials()

    cursor = mydb.cursor()
    cursor.execute("USE guildList")
    sql = "INSERT INTO Guilds (guildID,guildName,guildOwner) VALUES (%s,%s,%s)"
    val = (guild.id, str(guild.name), guild.owner.id)
    cursor.execute(sql, val)
    mydb.commit()
    
    create_new_guild_database(guild,mydb,cursor)

    mydb.close()

def update_channel(channel: discord.TextChannel):
    """Called when a channel is updated."""
    mydb = get_credentials(channel.guild.id)

    sql = ("UPDATE Channels SET channelName=%s,isNSFW=%s,isNews=%s,"+
           "categoryID=%s WHERE channelID=%s")
    val = (channel.name,channel.is_nsfw(),channel.is_news(),channel.category_id,
           channel.id)

    cursor = mydb.cursor()
    cursor.execute(sql,val)
    mydb.commit()
    mydb.close()

def delete_channel(channel: discord.TextChannel):
    """Called when a channel is deleted"""
    mydb = get_credentials(channel.guild.id)

    sql = ("UPDATE Channels SET isDeleted=True WHERE channelID=%s")
    val = (channel.id,)

    cursor = mydb.cursor()
    cursor.execute(sql,val)
    mydb.commit()
    mydb.close()

def update_guild(guild: discord.Guild):
    """Called when a guild is updated."""
    mydb = get_credentials()
    cursor = mydb.cursor()
    cursor.execute("USE guildList")

    sql = "UPDATE Guilds SET guildName=%s WHERE guildID=%s"
    val = (guild.name,guild.id)
    cursor.execute(sql,val)
    mydb.commit()
    mydb.close()
