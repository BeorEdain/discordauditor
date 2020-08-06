import os
from datetime import datetime

import discord
from mysql.connector import (
    IntegrityError, MySQLConnection, ProgrammingError, connect)

time_format = "%Y-%m-%d %H:%M:%S"

attach_path = "discordauditor/"

if not os.path.isdir(attach_path):
    os.mkdir(attach_path)

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

            directory = attach_path + server
            if not os.path.isdir(directory):
                os.makedirs(attach_path + server)
            
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

async def guild_join(guild: discord.Guild):
    """Called when a new guild is added."""
    mydb = get_credentials()

    cursor = mydb.cursor()
    cursor.execute("USE guildList")
    sql = ("INSERT INTO Guilds (guildID,guildName,guildOwner,enrolledOn)VALUES"+
          "(%s,%s,%s,%s)")
    val = (guild.id, str(guild.name), guild.owner.id,
           datetime.utcnow().strftime(time_format))
    try:
        cursor.execute(sql, val)
        mydb.commit()
        build_database("guildList", cursor)
    except IntegrityError:
        print("Rejoined previously enrolled server")

    mydb.close()

    # for channel in guild.channels:
    #     new_channel(channel)
    
    channel_check(guild)
    member_check(guild)
    await message_check(guild)

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

def guild_leave(guild: discord.Guild):
    """Called when the bot is kicked from a guild."""
    mydb = get_credentials()

    cursor = mydb.cursor()
    cursor.execute("USE guildList")
    sql = "UPDATE Guilds SET currentlyEnrolled=%s,oustedOn=%s WHERE guildID=%s"
    val = (False,datetime.utcnow().strftime(time_format),guild.id)

    cursor.execute(sql,val)
    mydb.commit()
    mydb.close()

def new_channel(channel: discord.TextChannel):
    """Called when a new channel is added to an audited server."""
    # Get the initial connection to the database.
    connection = get_credentials(channel.guild.id)

    if type(channel) == discord.TextChannel:
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

def build_database(comm: str, cursor, guildID = None):
    """
    Builds the database based on pre-built SQL queries.\n
    comm can be:\n
        guildList: Make the guildList database.
        server_database: A template for the individual databases.
    """
    command = ""
    if comm == "guildList":
        with open("sql/guild_database_creator.sql", 'rt') as sql_comm:
            command = sql_comm.read()

    elif comm == "server_database":
        with open("sql/database_creator.sql", 'rt') as sql_comm:
            command = sql_comm.read()
            cursor.execute(f"CREATE DATABASE {guildID}")
            cursor.execute(f"USE {guildID}")

    for cmd in cursor.execute(command, multi=True):
        cmd

def guild_check(client: discord.Client):
    """Run when there's a need to check the current guilds."""
    mydb = get_credentials()
    cursor = mydb.cursor()

    guilds = client.guilds
    # Instantiate a list for the guilds that the bot is currently in.
    guild_list = []

    # Go through each guild and grab the ID for it to reference later.
    for guild in guilds:
        guild_list.append(guild.id)

    # Instantiate the cursor and execute the above command.
    cursor = mydb.cursor()
    try:
        cursor.execute("USE guildList")

    # If the guild database doesn't exist.
    except ProgrammingError:
        build_database("guildList", cursor)
     
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
        cursor.executemany(sql, vals)
        mydb.commit()
        mydb.close()

def channel_check(guild: discord.Guild):
    """Run when there's a need to check a guild's channels."""
    mydb = get_credentials()
    cursor = mydb.cursor()
    # Instantiate a list for the channels that the bot can access.
    channel_list = []
    # database = f"server{str(guild[0])}"
    database = "server" + str(guild.id)
    try:
        cursor.execute(f"USE {database}")
    except ProgrammingError:
        # create_new_guild_database(guild[0], mydb, cursor)
        build_database("server_database", cursor, database)

    # for channel in client.get_guild(guild[0]).channels:
    for channel in guild.channels:
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
            specific_channel = guild.get_channel(channel)

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
        mydb.close()

def member_check(guild: discord.Guild):
    """Run when there's a need to check for new members."""
    mydb = get_credentials()
    cursor = mydb.cursor()

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

    mydb.close()

async def message_check(guild: discord.Guild):
    """Run when there's a need to check a guild's messages."""
    mydb = get_credentials()
    cursor = mydb.cursor()
    # Instantiate a list for the raw messages.
    raw_messages = []
    # Specify which database to use.
    cursor.execute(f"USE server{guild.id}")
    
    # Go through each channel
    for channel in guild.channels:
        # Only worry about text channels.
        if type(channel) == discord.channel.TextChannel:
            raw_messages = (raw_messages +
                            await channel.history(limit=None).flatten())

    # Reverse the raw messages so they're in order from oldest to newest.
    raw_messages.reverse()

    # Get a list of messages that are already in the server.
    cursor.execute("SELECT messageID,hasAttachment,qualifiedName FROM Messages")
    records = cursor.fetchall()

    # Convert tuple'd records from SQL to simple list.
    message_list = []
    for row in records:
        if row[0] not in message_list:
            message_list.append(row[0])

    # Use that list to remove any messages that are already in the server
    # from the raw message list.
    clean_messages = []
    attachment_list = []
    for mess in raw_messages:
        if mess.id not in message_list:
            clean_messages.append(mess)

        if mess.attachments:
            attachment_list.append(mess)

    # Instantiate two lists, one for messages with attachments and one for
    # messages without.
    to_upload_no_attach = []
    to_upload_attach = []

    directory = attach_path + f"server{guild.id}/"

    # If the attachment directory doesn't exist, create it.
    if not os.path.isdir(directory):
        os.mkdir(directory)

    # If there's an attachment.
    for attachment in attachment_list:
        # Get the full path and filename for it.
        filename = (directory + str(attachment.attachments[0].id) +
                   attachment.attachments[0].filename)

        # If that file doesn't exist, create it.
        if not os.path.isfile(f"{directory}{attachment.attachments[0].id}"+
                              f"{attachment.attachments[0].filename}"):
            await discord.Attachment.save(attachment.attachments[0], filename)

    # If there are messages to add.
    if len(clean_messages) > 0:
        for message in clean_messages:
            # If the message has one or more attachments.
            if message.attachments:
                for attachment in message.attachments:
                    to_upload_attach.append((message.id, message.channel.id,
                            message.author.id, message.created_at,
                            message.content, True, attachment.id,
                            attachment.filename, str(message.id) +
                            attachment.filename, attachment.url))
            
            # If the message has no attachments.
            else:
                to_upload_no_attach.append((message.id, message.channel.id,
                        message.author.id, message.created_at,
                        message.content))
        
        raw_messages.clear()

    # If there are attachment messages to add to the database.
    if len(to_upload_attach) > 0:
        sql = ("INSERT INTO Messages (messageID, channelID, authorID,"+
                "dateCreated, message, hasAttachment, attachmentID,"+
                "filename, qualifiedName, url) VALUES"+
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)")
        
        cursor.executemany(sql, to_upload_attach)
        mydb.commit()

    # If there are non-attachment messages to add to the database.
    if len(to_upload_no_attach) > 0:
        sql = ("INSERT INTO Messages (messageID, channelID, authorID,"+
                "dateCreated, message) VALUES (%s,%s,%s,%s,%s)")
        
        cursor.executemany(sql, to_upload_no_attach)
        mydb.commit()
        mydb.close()
