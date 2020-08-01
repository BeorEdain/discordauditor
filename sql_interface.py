import discord
from datetime import datetime
from mysql.connector import (
    IntegrityError, MySQLConnection, ProgrammingError, connect)

time_format = "%Y-%m-%d %H:%M:%S"

def get_credentials() -> MySQLConnection:
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
    # TODO: If exception is raised, revert to manual input from user and save
    # output to the file.
    except FileNotFoundError:
        print("database_credentials does not exist.")
        exit()

    # Try the connection.
    try:
        mydb = connect(
            host=credentials[0],
            user=credentials[1],
            password=credentials[2],
            database=credentials[3])
        
        return mydb

    # If the connection cannot be established due to input error, log and quit.
    except ProgrammingError:
        print("There was an error with the credentials.")
        exit()

def new_message(message: discord.Message):
    """Called when a new message is added to an audited server."""
    # Get the initial connection to the database
    connection = get_credentials()

    # Select only the members who have a matching memberID (Hint, there's only
    # ever going to be one as it's the primary key of the member table).
    sql = "SELECT * FROM Members WHERE memberID = %s"
    val = (message.author.id,)

    # Create the cursor and execute the command.
    cursor = connection.cursor()
    cursor.execute(sql, val)

    # Get the results of the previous command.
    records = cursor.fetchall()

    cursor.reset()

    # If there is no results, then the member doesn't exist in the table yet, so
    # they need to be added.
    if len(records) == 0:
        # Build the SQL command.
        sql = ("INSERT INTO Members (memberID,memberName,discriminator,isBot,"+
                "nickname,guildID) VALUES (%s,%s,%s,%s,%s,%s)")
        
        # Add the values to a tuple.
        val = (message.author.id,message.author.name,
                    message.author.discriminator,message.author.bot,
                    message.author.nick,message.author.guild.id)
        
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
    connection = get_credentials()

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
    connection = get_credentials()

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
    connection = get_credentials()

    # Set up the prepared statement to insert the new channel in to the table.
    sql = ("INSERT INTO Channels (channelID, channelName, isNSFW, isNews,"+
           "categoryID, guildID) VALUES (%s,%s,%s,%s,%s,%s)")
    val = (channel.id, channel.name, channel.is_nsfw(), channel.is_news(),
           channel.category_id, channel.guild.id)

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

    # Get all of the guild IDs from the Guilds table.
    sql = "SELECT guildID FROM Guilds"

    # Instantiate the cursor and execute the above command.
    cursor = mydb.cursor()
    cursor.execute(sql)

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
        sql = "INSERT INTO Guilds (guildID, guildName) VALUES (%s,%s)"

        # Instantiate an empty list for the values.
        vals = []

        # Go through each guild in the guild_list.
        for guild in guild_list:
            # Use the guild ID to get the information about the specific guild.
            specific_guild = client.get_guild(guild)

            # Add the guild ID and guild name to the second part of the prepared
            # statement as a tuple.
            vals.append((specific_guild.id, specific_guild.name))

        # Add each of the tuples to the database.
        for value in vals:
            cursor.execute(sql, value)
            mydb.commit()

    # END GUILD CHECK ##########################################################
    # BEGIN CHANNEL CHECK ######################################################
    # Instantiate a list for the channels that the bot can access.
    channel_list = []

    # Go through each channel in each guild and grab the ID for reference later.
    for guild in guilds:
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
        # Build the prepared statement to insert the values for the channels.
        sql = ("INSERT INTO Channels (channelID, channelName, isNSFW, isNews," +
              "categoryID, guildID) VALUES (%s,%s,%s,%s,%s,%s)")
        
        # Instantiate an empty list for the values.
        vals = []

        # Go through each channel in the channel_list
        for channel in channel_list:
            # Use the channel ID to get the information about the specific
            # channel.
            specific_channel = client.get_channel(channel)

            # Add the channel ID, name, whether it's NSFW, whether it's news,
            # the category ID (if there is one), and the guild ID to the second
            # part of the prepared statement as a tuple.
            vals.append((specific_channel.id, specific_channel.name,
                         specific_channel.is_nsfw(), specific_channel.is_news(),
                         specific_channel.category_id,
                         specific_channel.guild.id))
        
        # Add each of the tuples to the database.
        for value in vals:
            cursor.execute(sql, value)
            mydb.commit()

    # END CHANNEL CHECK ########################################################
    # BEGIN MESSAGE CHECK ######################################################

    raw_messages = []
    for guild in client.guilds:
        for channel in guild.channels:
            if type(channel) == discord.channel.TextChannel:
                raw_messages = (raw_messages +
                               await channel.history(limit=None).flatten())

    sql = "SELECT messageID FROM Messages"

    cursor.execute(sql)
    records = cursor.fetchall()

    # Convert tuple'd records from SQL to simple list.
    message_ID_list = []
    for row in records:
        message_ID_list.append(row[0])

    # Use that list to remove any messages that are already in the server from
    # the raw message list.
    for mess in raw_messages:
        if mess.id in message_ID_list:
            raw_messages.remove(mess)

    # if len(raw_messages) > 0:
    #     for message in raw_messages:
    #         new_message(message)

    to_upload_no_attach = []
    to_upload_attach = []

    if len(raw_messages) > 0:
        for message in raw_messages:
            if message.attachments:
                for attachment in message.attachments:
                    to_upload_attach.append((message.id, message.channel.id,
                            message.author.id, message.created_at,
                            message.content, True, attachment.id,
                            attachment.filename, attachment.url))
            else:
                to_upload_no_attach.append((message.id, message.channel.id,
                        message.author.id, message.created_at, message.content))

    sql = ("INSERT INTO Messages (messageID, channelID, authorID, dateCreated,"+
           "message, hasAttachment, attachmentID, filename, url) VALUES "+
           "(%s,%s,%s,%s,%s,%s,%s,%s,%s)")
    
    cursor.executemany(sql, to_upload_attach)
    mydb.commit()

    sql = ("INSERT INTO Messages (messageID, channelID, authorID, dateCreated,"+
           "message) VALUES (%s,%s,%s,%s,%s)")
    
    cursor.executemany(sql, to_upload_no_attach)
    mydb.commit()