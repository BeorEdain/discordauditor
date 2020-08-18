import configparser
import logging
import os
import sys
from datetime import datetime

import discord
from mysql.connector import (DatabaseError, IntegrityError, InterfaceError,
                             MySQLConnection, OperationalError,
                             ProgrammingError, connect)

# Initialize the configuration file in memory.
config = configparser.ConfigParser()

# Read the configuration file into memory. Doesn't need to be in a try/except
# catch because the file is checked for and created if necessary in the 
# discord_auditor.py file.
config.read(r'config.ini')

# Initialize the logger.
logger = logging.getLogger(__name__)

# Get the log level from the config file.
log_level=config.get("logger","log_level")

# Get the appropriate level of logging according to the config file.
if log_level=="DEBUG":
    log_level=logging.DEBUG
elif log_level=="INFO":
    log_level=logging.INFO
elif log_level=="WARNING":
    log_level=logging.WARNING
elif log_level=="ERROR":
    log_level=logging.ERROR
elif log_level=="CRITICAL":
    log_level=logging.CRITICAL

# Set the level of the logger according to the config file.
logger.setLevel(log_level)

# Format the logger.
formatter = logging.Formatter('%(asctime)s; %(levelname)s; %(filename)s; '+
                                '%(funcName)s; %(message)s')

log_path = config.get("logger","log_path")
log_name = config.get("logger","log_filename")
log_type = config.get("logger","log_file_type")
log_number = 0

if not os.path.isdir(log_path):
    os.mkdir(log_path)

while os.path.isfile(log_path + log_name + str(log_number) + "." + log_type):
    log_number = log_number + 1

# Build the file name for the log.
log_filename = log_path + log_name + str(log_number) + "." + log_type

# Set the name of the log file according to the config file.
handler = logging.FileHandler(log_filename)

# Add the log format to the handler.
handler.setFormatter(formatter)

# Add the handler to the logger.
logger.addHandler(handler)

# If the config specifies to use the console as well as a file to output.
if config.get("logger","log_term_output"):
    handler2 = logging.StreamHandler(sys.stdout)
    handler2.setLevel(log_level)
    handler2.setFormatter(formatter)
    logger.addHandler(handler2)        

# Set the appropriate time format for both MySQL and Discord.
time_format = "%Y-%m-%d %H:%M:%S"

# Get the attachment path the bot will use.
attach_path = config.get("attach_path","path")

# Create the directory if it doesn't exist already.
if not os.path.isdir(attach_path):
    logger.warning(f"\'{attach_path}\' does not exist. Creating.")
    os.mkdir(attach_path)

# Create the logs/ directory if it doesn't exist already.
if not os.path.isdir("logs/"):
    logger.warning("\'logs/\' does not exist. Creating.")
    os.mkdir("logs/")

async def new_message(message: discord.Message):
    """
    Called when a new message is added to an audited server.\n
    message: The message that is going to be added.
    """
    logger.info(f"\'{message.author.name}\' wrote a message in "+
                 f"\'{message.guild.name}\' in the \'{message.channel.name}\' "+
                 "channel.")

    # Set up the cursor.
    cursor = ""

    # Try to set up the cursor.
    try:
        cursor = mydb.cursor()
    
    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")

    # Switch to the appropriate database.
    logger.debug(f"Switching to \'server{message.guild.id}\'.")

    # Try to use the guild database.
    try:
        cursor.execute(f"USE server{message.guild.id}")
    
    except ProgrammingError as err:
        logger.critical(f"Could not connect to {message.guild.id}.\n{err}")

    # Select only the members who have a matching memberID (Hint, there's only
    # ever going to be one as it's the primary key of the member table).
    sql = "SELECT * FROM Members WHERE memberID = %s"
    val = (message.author.id,)

    # Execute the command.
    try:
        cursor.execute(sql, val)
    
    except ProgrammingError as err:
        logger.critical(f"Could not execute the command {sql}.\n{err}")

    # Initialize the records so they can be in a try/except catch.
    records = ""
    
    # Try to get all of the records.
    try:
        records = cursor.fetchall()

    except InterfaceError as err:
        logger.critical(f"Could not fetch the records.\n{err}")

    # Fetch all of the information about the member in a digestable manner.
    member_ID = message.author.id
    member_name = message.author.name
    member_discriminator = int(message.author.discriminator)
    member_is_bot = int(message.author.bot)
    member_nickname = message.author.nick

    # Create a tuple out of the data.
    member = (member_ID,member_name,member_discriminator,member_is_bot,
              member_nickname)

    sql=("UPDATE Members SET memberName=%s, discriminator=%s, nickname=%s "+
         "WHERE memberID=%s")
    vals = []

    # Compare the information about the member on file against the information
    # returned from Discord.
    for row in records:
        if row != member:
            logger.info(f"Member \'{message.author.name}\' needs to be "+
                         "updated.")
            vals.append((member_name,member_discriminator,member_nickname,
                        member_ID))

    try:
        cursor.executemany(sql,vals)
    
    except (ProgrammingError, InterfaceError) as err:
        logger.critical(f"User {message.author.name} could not be updated.\n"+
                        f"{err}")

    mydb.commit()

    # If there is no results, then the member doesn't exist in the table yet, so
    # they need to be added.
    if len(records) == 0:
        logger.info(f"\'{message.author.id}\' has never written in "+
                     f"\'{message.guild.name}\' before. Adding to Members.")

        # Build the SQL command.
        sql = ("INSERT INTO Members (memberID,memberName,discriminator,isBot,"+
               "nickname) VALUES (%s,%s,%s,%s,%s)")
        
        # Add the values to a tuple.
        val = (message.author.id,message.author.name,
               message.author.discriminator,message.author.bot,
               message.author.nick)
        
        # Execute the command.
        try:
            cursor.execute(sql, val)
        
        except ProgrammingError as err:
            logger.critical(f"Could not execute the command {sql}.\n{err}")

        mydb.commit()

    # Create the command to add the message to the Messages table.
    if message.attachments:
        logger.debug("This message has an attachment.")

        # Go through each attachment in the message.
        for attachment in message.attachments:
            sql = ("INSERT INTO Messages (messageID,channelID,authorID,"+
                   "dateCreated,message,hasAttachment,attachmentID,filename,"+
                   "qualifiedName,url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)")

            # Add the values of the message as a tuple.
            qualified_name = str(attachment.id) + str(attachment.filename)
            val = (message.id, message.channel.id, message.author.id,
                   message.created_at, message.content, True, attachment.id,
                   attachment.filename, qualified_name, attachment.url)

            directory = ""
            server = f"server{message.guild.id}/"

            directory = attach_path + server
            if not os.path.isdir(directory):
                os.makedirs(attach_path + server)
            
            directory = (directory + str(message.attachments[0].id)+
                            message.attachments[0].filename)

            if not os.path.isfile(directory):
                await discord.Attachment.save(message.attachments[0],directory)

    # If there are no attachments in the message.
    else:
        logger.debug("This message has no attachments.")

        sql = ("INSERT INTO Messages (messageID, channelID, authorID,"+
               "dateCreated, message) VALUES (%s,%s,%s,%s,%s)")
        val = (message.id, message.channel.id, message.author.id,
               message.created_at, message.content)

    # Execute the command, commit it to the database, and close the cursor.
    try:
        cursor.execute(sql, val)
    
    except ProgrammingError as err:
        logger.critical(f"Could not execute the command {sql}.\n{err}")

    mydb.commit()
    cursor.close()

def edited_message(message: discord.Message):
    """
    Called when a message is edited in an audited server.\n
    message: The message that has been edited.
    """
    # Set up the cursor.
    cursor = ""

    try:
        cursor = mydb.cursor()
    
    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")
    
    try:
        cursor.execute(f"USE server{message.guild.id}")
    
    except ProgrammingError as err:
        logger.critical(f"The \'{message.guild.name}\' database could not be "+
                        f"accessed.\n{err}")
        
    current_time = datetime.utcnow().strftime(time_format)

    logger.info(f"\'{message.author.name}\' edited a message in "+
                f"\'{message.guild.name}\' in the {message.channel.name} "+
                "channel.")

    # Set the prepared statement to update the appropriate values.
    sql = "UPDATE Messages SET isEdited=%s, dateEdited=%s WHERE messageID=%s"
    val = (True,current_time,message.id)

    # Execute the command, commit it to the database, then close the cursor.
    try:
        cursor.execute(sql, val)
    
    except ProgrammingError as err:
        logger.critical(f"Could not execute the command {sql}.\n{err}")

    mydb.commit()
    cursor.close()

def deleted_message(message: discord.Message):
    """
    Called when a message is deleted from an audited server.\n
    message: The message that has been deleted.
    """
    # Set up the cursor.
    cursor = ""
    
    try:
        cursor = mydb.cursor()
    
    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")

    try:
        cursor.execute(f"USE server{message.guild.id}")

    except ProgrammingError as err:
        logger.critical(f"The \'{message.guild.name}\' database could not be "+
                        f"accessed.\n{err}")

    # Get the current UTC time to record when the message was deleted.
    current_time = datetime.utcnow().strftime(time_format)

    logger.info(f"A message was deleted from \'{message.guild.name}\' in the "+
                f"{message.channel.name} channel.")

    # Set up the prepared statement set the message as deleted and by whom.
    sql = "UPDATE Messages SET isDeleted=%s, dateDeleted=%s WHERE messageID=%s"
    val = (True,current_time,message.id)

    # Execute the command, commit it to the database, then close the cursor.
    try:
        cursor.execute(sql, val)
    
    except ProgrammingError as err:
        logger.critical(f"Could not execute the command {sql}.\n{err}")

    mydb.commit()
    cursor.close()

def member_join(member: discord.Member):
    """
    Called when a new member joins a guild.\n
    member: The member who joined the guild.
    """
    logger.info(f"User \'{member.name}\' has joined \'{member.guild.name}\'.")

    cursor = mydb.cursor()

    sql = f"USE server{member.guild.id}"

    logger.debug(f"Switching to \'server{member.guild.id}\'.")
    cursor.execute(sql)

    sql = ("INSERT INTO Members (memberID,memberName,discriminator,isBot,"+
          "nickname) VALUES (%s,%s,%s,%s,%s)")
    val = (member.id,member.name,member.discriminator,member.bot,member.nick)

    try:
        cursor.execute(sql,val)

    except IntegrityError:
        logger.warning(f"User \'{member.name}\' has rejoined "+
                       f"\'{member.guild.name}\'. Updating them now.")
        
        sql = ("UPDATE Members SET memberName=%s,discriminator=%s,nickname=%s "+
               "WHERE memberID=%s")

        val = (member.name,member.discriminator,member.nick,member.id)

        cursor.execute(sql,val)

    mydb.commit()
    cursor.close()

def member_update(before: discord.Member, after: discord.Member):
    """
    Called when a member updates their nickname.\n
    before: The member before the change.\n
    after:  The member after the change.
    """
    logger.info(f"User \'{before.name}\' changed their nickname to "+
                f"\'{after.nick}\' in \'{before.guild.name}\'.")

    cursor = mydb.cursor()

    sql = f"USE server{before.guild.id}"

    logger.debug(f"Switching to \'server{before.guild.id}\'.")
    cursor.execute(sql)

    sql = ("UPDATE Members SET nickname=%s WHERE memberID=%s")
    
    val = (after.nick, before.id)

    cursor.execute(sql,val)
    mydb.commit()
    cursor.close()

def user_update(before: discord.User, after: discord.User):
    """
    Called when a user changes their username or discriminator.\n
    before: The member before the change.\n
    after:  The member after the change.
    """
    logger.info(f"User \'{before.name}#{before.discriminator}\' has been "+
                f"changed to \'{after.name}#{after.discriminator}")
    
    cursor = mydb.cursor()

    sql = f"USE server{before.guild.id}"

    logger.debug(f"Switching to \'server{before.guild.id}\'.")
    cursor.execute(sql)

    sql = ("UPDATE Members SET memberName=%s,discriminator=%s WHERE "+
           "memberID=%s")
    
    val = (after.name, after.discriminator, before.id)

    cursor.execute(sql,val)
    mydb.commit()
    cursor.close()

def voice_activity(member: discord.Member, before: discord.VoiceState,
                 after: discord.VoiceState):
    """
    Called when a user enters, leaves, or moves to another voice channel.\n
    member: The member who entered or left the voice chat.\n
    before: The voice state. Will be None if the user is entering the channel
    and they were not in another voice channel previously.\n
    after: The voice state. Will be None if the user is leaving the channel.
    """
    # Set up the cursor.
    cursor = ""
    
    try:
        cursor = mydb.cursor()

    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")

    try:
        cursor.execute(f"USE server{member.guild.id}")
    
    except ProgrammingError as err:
        logger.critical(f"The \'{member.guild.name}\' database could not be "+
                        f"accessed.\n{err}")
    
    # Initialize the SQL and value variables as well as get the current time.
    sql = ""
    val = ()
    time_now = datetime.utcnow().strftime(time_format)

    # If the member is entering a voice channel from no voice channel.
    # Meaning if they were not currently in a voice channel and they enter one.
    if not before.channel and after.channel:
        logger.info(f"\'{member.name}\' has entered the "+
                    f"\'{after.channel.name}\' voice channel in "+
                    f"\'{after.channel.guild.name}\'.")

        # Add a new line for this new entrance.
        sql = ("INSERT INTO VoiceActivity (memberID,channelID,dateEntered)"+
               "VALUES (%s,%s,%s)")
        val = (member.id,after.channel.id,time_now)

        try:
            cursor.execute(sql, val)
        
        except ProgrammingError as err:
            logger.critical(f"Could not execute the command {sql}.\n{err}")
    
    # If the member is entering a voice channel from another voice channel.
    # Meaning if they switch voice channels.
    elif before.channel and after.channel:
        logger.info(f"\'{member.name}\' has moved from the "+
                    f"\'{before.channel.name}\' voice channel to the "+
                    f"\'{after.channel.name}\' voice channel in "+
                    f"\'{after.channel.guild.name}\'.")

        # Update the previously null dateLeft for this user.
        sql=("UPDATE VoiceActivity SET dateLeft=%s WHERE memberID=%s order by "+
             "ID desc limit 1; ")
        
        # Insert a new line for this new entrance.
        sql=sql+("INSERT INTO VoiceActivity (memberID,channelID,dateEntered) "+
               "VALUES (%s,%s,%s)")
        val=(time_now,member.id,member.id,after.channel.id,time_now)

        # Since this is a multiline command, it needs special treatment.
        try:
            for cmd in cursor.execute(sql,val,multi=True):
                cmd
    
        except ProgrammingError as err:
            logger.critical(f"Could not execute the command {sql}.\n{err}")
        

    # If the member is leaving a voice channel and not going to any other.
    else:
        logger.info(f"\'{member.name}\' has left the "+
                    f"\'{before.channel.name}\' voice channel in "+
                    f"\'{before.channel.guild.name}\'.")

        sql=("UPDATE VoiceActivity SET dateLeft=%s WHERE memberID=%s order by "+
             "ID desc limit 1")
        val=(time_now,member.id)

        try:
            cursor.execute(sql,val)
    
        except ProgrammingError as err:
            logger.critical(f"Could not execute the command {sql}.\n{err}")
    
    # Commit the command to the database and close the cursor.
    mydb.commit()
    cursor.close()

async def guild_join(guild: discord.Guild, client: discord.Client):
    """
    Called when a new guild is added.\n
    gulid: The new guild that has been enrolled.
    client: The bot client. Used to get any members that left the server that
    left messages.
    """
    logger.info(f"\'{guild.name}\' has been enrolled.")

    # Set up the cursor.
    cursor = ""
    
    try:
        cursor = mydb.cursor()
    
    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")

    # Add the guild to the guildList database.
    try:
        cursor.execute("USE guildList")
    
    except ProgrammingError as err:
        logger.critical(f"Could not access the guildList database.{err}")

    sql = ("INSERT INTO Guilds (guildID,guildName,guildOwner,enrolledOn)VALUES"+
          "(%s,%s,%s,%s)")
    val = (guild.id, str(guild.name), guild.owner.id,
           datetime.utcnow().strftime(time_format))
    
    # Try to insert the guild.
    try:
        cursor.execute(sql,val)
        mydb.commit()
        build_server_database("server" + str(guild.id), cursor)
        
    # If the server already exists, update it.
    except IntegrityError:
        logger.warning(f"\'{guild.name}\' has been previously enrolled.")

        sql=("UPDATE Guilds SET guildName=%s,guildOwner=%s,enrolledOn=%s,"+
               "currentlyEnrolled=True,oustedOn=NULL WHERE guildID=%s")
        val=(guild.name,guild.owner.id,datetime.utcnow().strftime(time_format),
             guild.id)

        try:
            cursor.execute(sql,val)
    
        except ProgrammingError as err:
            logger.critical(f"Could not execute the command {sql}.\n{err}")

        mydb.commit()

    # Close the cursor.
    cursor.close()

    # Get all of the channels, members, and messages in the new or reenrolled
    # guild.
    channel_check(guild)
    member_check(guild)
    await message_check(guild, client)

def guild_update(guild: discord.Guild):
    """
    Called when a guild is updated.\n
    guild: The guild that has been updated.
    """
    logger.info(f"\'{guild.name}\' has been updated.")

    # Set up the cursor.
    cursor = ""
    
    try:
        cursor = mydb.cursor()
    
    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")

    # Connect to the guildList database.
    try:
        cursor.execute("USE guildList")
    
    except ProgrammingError as err:
        logger.critical(f"Could not access the guildList database.\n{err}")

    # Update the entry.
    sql = "UPDATE Guilds SET guildName=%s,guildOwner=%s WHERE guildID=%s"
    val = (guild.name,guild.owner.id,guild.id)

    try:
        cursor.execute(sql,val)

    except ProgrammingError as err:
        logger.critical(f"Could not execute the command {sql}.\n{err}")

    mydb.commit()

    # Close the cursor.
    cursor.close()

def guild_leave(guild: discord.Guild):
    """
    Called when the bot leaves a guild, either due to being kicked or told to
    leave.\n
    guild: The guild that the bot is no longer enrolled in.
    """
    logger.info(f"\'{guild.name}\' has been unenrolled.")

    # Set up the cursor.
    cursor = ""
    
    try:
        cursor = mydb.cursor()
    
    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")

    # Connecto to the guildList database.
    try:
        cursor.execute("USE guildList")

    except ProgrammingError as err:
        logger.critical(f"Could not access the guildList database.\n{err}")

    # Update the entry.
    sql = "UPDATE Guilds SET currentlyEnrolled=%s,oustedOn=%s WHERE guildID=%s"
    val = (False,datetime.utcnow().strftime(time_format),guild.id)

    try:
        cursor.execute(sql,val)

    except ProgrammingError as err:
        logger.critical(f"Could not execute the command {sql}.\n{err}")

    mydb.commit()

    # Close the cursor.
    cursor.close()

def new_channel(channel: discord.TextChannel):
    """
    Called when a new channel is added to an audited server.\n
    channel: the channel that has been created.    
    """
    logger.info(f"The \'{channel.name}\' channel has been created in the "+
                f"\'{channel.guild.name}\' guild.")

    # Set up the cursor.
    cursor = ""
    
    try:
        cursor = mydb.cursor()
    
    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")

    # Connect to the appropriate database.
    try:
        cursor.execute(f"USE server{channel.guild.id}")

    except ProgrammingError as err:
        logger.critical(f"Could not access the \'{channel.guild.name}\' "+
                        "database.\n{err}")

    # Insert the new channel.
    sql=("INSERT INTO Channels (channelID,channelName,channelTopic,"+
         "channelType,isNSFW,isNews,categoryID) VALUES (%s,%s,%s,%s,%s,%s,%s)")

    val=(channel.id,channel.name,channel.topic,str(channel.type),
         channel.is_nsfw(),channel.is_news(),channel.category_id)

    # Execute the command, commit it to the database, then close the cursor.
    try:
        cursor.execute(sql,val)

    except ProgrammingError as err:
        logger.critical(f"Could not execute the command {sql}.\n{err}")

    mydb.commit()
    cursor.close()

def update_channel(channel: discord.TextChannel):
    """
    Called when a channel is updated.\n
    channel: The channel that has been updated.
    """
    logger.info(f"Channel \'{channel.name}\' has been updated in the "+
                 f"\'{channel.guild.name}\' guild.")

    # Set up the cursor.
    cursor = ""
    
    try:
        cursor = mydb.cursor()
    
    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")

    # Connect to the appropriate database.
    try:
        cursor.execute(f"USE server{channel.guild.id}")
    
    except ProgrammingError as err:
        logger.critical(f"Could not access the \'{channel.guild.name}\' "+
                        f"database.\n{err}")

    # Update the channel with the new information.
    sql = ("UPDATE Channels SET channelName=%s,channelTopic=%s,isNSFW=%s,"+
           "isNews=%s,categoryID=%s WHERE channelID=%s")
    val = (channel.name,channel.topic,channel.is_nsfw(),channel.is_news(),
           channel.category_id,channel.id)

    # Execute the command, commit it to the database, then close the cursor.
    try:
        cursor.execute(sql,val)

    except ProgrammingError as err:
        logger.critical(f"Could not execute the command {sql}.\n{err}")

    mydb.commit()
    cursor.close()

def delete_channel(channel: discord.TextChannel):
    """
    Called when a channel is deleted.\n
    channel: The channel that has been deleted.
    """
    logger.info(f"Channel \'{channel.name}\' has been deleted from the "+
                f"\'{channel.guild.name}\' guild.")

    # Set up the cursor.
    try:
        cursor = mydb.cursor()
    
    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")

    # Connect to the appropriate database.
    try:
        cursor.execute(f"USE server{channel.guild.id}")
    
    except ProgrammingError as err:
        logger.critical(f"Could not access the \'{channel.guild.name}\' "+
                        f"database.\n{err}")

    # Mark the appropriate channel as deleted.
    sql = ("UPDATE Channels SET isDeleted=True WHERE channelID=%s")
    val = (channel.id,)

    # Execute the command, commit it to the database, then close the cursor.
    try:
        cursor.execute(sql,val)

    except ProgrammingError as err:
        logger.critical(f"Could not execute the command {sql}.\n{err}")
        
    mydb.commit()
    cursor.close()

def build_guild_database(cursor):
    """
    Builds the guildList database that houses all of the information about each
    guild.\n
    cursor: The cursor for the MYSQL connection so multiple links are not
    needed.
    """
    logger.debug("Building the guild database.")
    command = ""

    # Get the commands from the file.
    logger.debug("Accessing the guild_database_creator.sql file")
    with open("sql/guild_database_creator.sql", 'rt') as sql_comm:
        command = sql_comm.read()
    
    # Iterate through each command and execute it.
    try:
        for cmd in cursor.execute(command, multi=True):
            # Ignore this. It's only here so 'cmd' doesn't throw as a problem by
            # the linter. It's not a problem, but it is annoying.
            cmd

    except DatabaseError as err:
        logger.critical("There was an issue creating the guild database."+
                     f"\n{err}")

def build_server_database(guildID: str, cursor):
    """
    Builds the database based on pre-built SQL queries.\n
    guildID: The ID for the guild in the "server + ID" format.\n
    cursor: The cursor for the MySQL connection so multiple links are not
    needed.
    """
    logger.debug(f"Building the {guildID} database.")

    # Create the new database.
    try:
        cursor.execute(f"CREATE DATABASE {guildID}")
    
    except (DatabaseError, ProgrammingError) as err:
        logger.critical("There was an issue creating the guild database."+
                     f"\n{err}")

    # Switch to the new database.
    cursor.execute(f"USE {guildID}")

    command = ""

    # Open the file with the commands for the new database.
    with open("sql/database_creator.sql", 'rt') as sql_comm:
        command = sql_comm.read()

    # Iterate through each command and execute it.
    try:
        for cmd in cursor.execute(command, multi=True):
            # Ignore this. It's only here so 'cmd' doesn't throw as a problem by
            # the linter. It's not a problem, but it is annoying.
            cmd

    except DatabaseError as err:
        logger.critical(f"There was an issue creating the {guildID} database."+
                     f"\n{err}")

def guild_check(client: discord.Client):
    """
    Run when there's a need to check the current guilds.\n
    client: The bot client. Used to determine which guilds are currently
    enrolled.
    """
    logger.info("Getting the list of currently enrolled guilds.")

    # Set up the cursor.
    cursor = ""
    
    try:
        cursor = mydb.cursor()
    
    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")

    # Get the list of currently enrolled guilds from Discord.
    guilds = client.guilds

    # Instantiate a list for the guilds that the bot is currently in.
    new_guilds = []
    reenrolled_guilds = []
    unenrolled_guilds = []

    # Go through each guild and grab the ID for it to reference later.
    for guild in guilds:
        new_guilds.append(guild.id)

    # Try to connect to the guildList database.
    try:
        cursor.execute("USE guildList")

    # If the guildList database doesn't exist.
    except ProgrammingError:
        logger.warning("Guild database does not exist. Creating.")
        build_guild_database(cursor)
     
    # Get all of the guilds and whether or not they're currently enrolled
    # according to the guildList database.
    try:
        cursor.execute("SELECT guildID,guildName,guildOwner,currentlyEnrolled "+
                       "FROM Guilds")
    
    except ProgrammingError as err:
        logger.critical(f"There was an error selecting from Guilds.\n{err}")

    # Record the response from the server.
    records = ""
    try:
        records = cursor.fetchall()
    
    except InterfaceError as err:
        logger.critical(f"There was an error fetching records.\n{err}")

    updated_guilds = []

    # Go through each record to ensure that all of the currently enrolled guilds
    # are part of the database.
    for row in records:
        test_guild = client.get_guild(row[0])

        guild_tuple = (test_guild.id,test_guild.name,test_guild.owner.id,True)

        if guild_tuple != row:
            updated_guilds.append((guild_tuple[1],guild_tuple[2],
                                   guild_tuple[0]))

        # If the guild is currently enrolled and is marked as such, remove it
        # because we don't need to do anything with it.
        if row[0] in new_guilds and row[3]:
            new_guilds.remove(row[0])

        # If the guild is currently enrolled but is marked as unenrolled, add it
        # to the reenrolled list.
        elif row[0] in new_guilds and not row[3]:
            reenrolled_guilds.append(row[0])

        # If the guild is not currently enrolled but is marked as being enrolled
        # then add it to the unenrolled list.
        elif row[0] not in new_guilds and row[3]:
            unenrolled_guilds.append(row[0])

    if len(updated_guilds) > 0:
        logger.info(f"{len(updated_guilds)} guilds have been updated since "+
                    "reawakening. Updating them now.")
        
        sql=("UPDATE Guilds SET guildName=%s,guildOwner=%s WHERE guildID=%s")

        cursor.executemany(sql,updated_guilds)
        mydb.commit()
    
    else:
        logger.debug("No enrolled guilds have been updated.")

    # If there are any left in the list of enrolled guilds.
    if len(new_guilds) > 0:
        logger.info(f"There are {len(new_guilds)} new guilds. Adding.")
        # Build the prepared statement to insert the values for the guild.
        sql = ("INSERT INTO Guilds (guildID,guildName,guildOwner,enrolledOn)"+
               "VALUES (%s,%s,%s,%s)")

        # Instantiate an empty list for the values.
        vals = []

        # Go through each guild in the new_guilds.
        for guild in new_guilds:
            # Use the guild ID to get the information about the specific guild.
            specific_guild = client.get_guild(guild)

            # Add the guild ID and guild name to the second part of the prepared
            # statement as a tuple.
            vals.append((specific_guild.id, specific_guild.name,
                         specific_guild.owner.id,
                         datetime.utcnow().strftime(time_format)))

        try:
            cursor.executemany(sql,vals)

        except Exception as err:
            logger.critical(f"There was an error executing a command.\n{err}")

        mydb.commit()
    
    # Mention in the log that there are no new guilds.
    else:
        logger.debug("There are no new guilds to be added.")

    # If there are guilds that are reenrolled, update the entries.
    if len(reenrolled_guilds) > 0:
        logger.info(f"There are {len(reenrolled_guilds)} reenrolled guilds. "+
                    "Updating.")
        sql = ("UPDATE Guilds SET currentlyEnrolled=True,oustedOn=NULL "+
               "WHERE guildID=%s")
        vals = []
        for guild in reenrolled_guilds:
            specific_guild = client.get_guild(guild)
            vals.append((specific_guild.id,))

        try:
            cursor.executemany(sql,vals)

        except Exception as err:
            logger.critical(f"There was an error executing a command.\n{err}")

        mydb.commit()
    
    # Mention in the log that there are no reenrolled guilds.
    else:
        logger.debug("There are no reenrolled guilds to be updated.")

    # If there are guilds that have been unenrolled, update the entries.
    if len(unenrolled_guilds) > 0:
        logger.info(f"There are {len(unenrolled_guilds)} unenrolled guilds. "+
                    "Marking them as such.")
        sql = ("UPDATE Guilds SET currentlyEnrolled=False,oustedOn=%s "+
               "WHERE guildID=%s")
        vals = []
        for guild in unenrolled_guilds:
            vals.append((datetime.utcnow().strftime(time_format),guild))

        # Add each of the tuples to the database.
        try:
            cursor.executemany(sql,vals)

        except Exception as err:
            logger.critical(f"There was an error executing a command.\n{err}")

        mydb.commit()
    
    # Mention in the log that there are no unerolled guilds.
    else:
        logger.debug("There are no unenrolled guilds.")
    
    cursor.close()
    logger.info("Guild check complete.")

def channel_check(guild: discord.Guild):
    """
    Run when there's a need to check a guild's channels.\n
    guild: The guild that the bot will get the channels for.
    """
    logger.info(f"Checking for new channels in \'{guild.name}\'.")

    # Set up the cursor.
    cursor = ""
    
    try:
        cursor = mydb.cursor()
    
    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")

    # Instantiate a list for the channels that the bot can access.
    channel_list = []
    database = "server" + str(guild.id)

    # Try to connect to the database.
    try:
        cursor.execute(f"USE {database}")

    # If it doesn't exist, build it.
    except ProgrammingError:
        logger.warning(f"The \'{guild.name}\' database does not exist. "+
                       "Creating.")
        build_server_database(database, cursor)

    for channel in guild.channels:
        # Only grab the IDs of the channels.
        channel_list.append(channel.id)

        # If this channel is a voice channel, get all of the members in it
        # currently.
        users_in_voice = []
        if str(channel.type) == "voice":
            users_in_voice = channel.members
        
        # Get a list of the user IDs as that's all that is necessary.
        users_in_voice_list = []
        for user in users_in_voice:
            users_in_voice_list.append(user.id)

        # Get the list of members who are currently listed as being in a voice
        # channel.
        try:
            cursor.execute("SELECT memberID FROM VoiceActivity WHERE dateLeft "+
                           "IS NULL")

        except ProgrammingError as err:
            logger.critical(f"There was an error selecting members.\n{err}")

        try:
            records = cursor.fetchall()
        
        except InterfaceError as err:
            logger.critical(f"There was an error retrieving records.\n{err}")

        # Go through each user that's marked as in a voice channel.
        for row in records:
            # If they are not currently in a voice channel, update them as
            # left with the current time.
            if row[0] not in users_in_voice_list:
                sql=("UPDATE VoiceActivity SET dateLeft=%s WHERE memberID=%s "+
                     "order by ID desc limit 1")
                val=(datetime.utcnow().strftime(time_format),guild.
                     get_member(row[0]).id)
                try:
                    cursor.execute(sql,val)

                except Exception as err:
                    logger.critical(f"There was an error executing a command."+
                                    f"\n{err}")

        # If there are users in the voice channel, then add them to the
        # database.
        for user in users_in_voice:
            sql = ("INSERT INTO VoiceActivity (memberID,channelID,dateEntered)"+
               "VALUES (%s,%s,%s)")
            val = (user.id,channel.id,datetime.utcnow().strftime(time_format))
            try:
                cursor.execute(sql,val)

            except Exception as err:
                logger.critical(f"There was an error executing a command."+
                                f"\n{err}")

        mydb.commit()

    # Get all of the chennel IDs from the Channels table.
    sql = "SELECT * FROM Channels"

    # Instantiate the cursor and execute the above command.
    try:
        cursor.execute(sql)
        records = cursor.fetchall()
    
    except Exception as err:
        logger.critical(f"There was an issue with the channels.\n{err}")

    updated_channels = []

    # Go through each record to ensure that all of the currently enrolled
    # channels are part of the database.
    for row in records:
        test_channel = guild.get_channel(row[0])

        channel_tuple = ()

        if str(test_channel.type) == "text":
            channel_tuple=(test_channel.id,test_channel.name,test_channel.topic,
                           str(test_channel.type),test_channel.is_nsfw(),
                           test_channel.is_news(),test_channel.category_id)

        else:
            channel_tuple=(test_channel.id,test_channel.name,"NULL",
                           str(test_channel.type),False,False,
                           test_channel.category_id)

        if channel_tuple != row:
            # Can't just add the channel_tuple to the list as the channelID
            # needs to be last as that's the order the SQL command requires.
            updated_channels.append((channel_tuple[1],channel_tuple[2],
                                     channel_tuple[3],channel_tuple[4],
                                     channel_tuple[5],channel_tuple[6],
                                     channel_tuple[0]))

        if row[0] in channel_list:
            channel_list.remove(row[0])

    if len(updated_channels) > 0:
        logger.info(f"{len(updated_channels)} channels have been updated in "+
                    f"\'{guild.name}\' since reawakening. Updating them now.")
        
        sql=("UPDATE Channels SET channelName=%s,channelTopic=%s,"+
             "channelType=%s,isNSFW=%s,isNews=%s,categoryID=%s WHERE "+
             "channelID=%s")
            
        cursor.executemany(sql,updated_channels)

    else:
        logger.debug(f"No channels have been modified in \'{guild.name}\' "+
                     "since reawakening.")

    # If there are any left in the list of enrolled channels.
    if len(channel_list) > 0:
        logger.info(f"There have been {len(channel_list)} channels created in "+
                    f"\'{guild.name}\' since reawakening. Adding them now.")
        # Build the prepared statement to insert the values for the
        # channels.
        sql=("INSERT INTO Channels (channelID,channelName,channelTopic,"+
             "channelType,isNSFW,isNews,categoryID) VALUES "+
             "(%s,%s,%s,%s,%s,%s,%s)")
        
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
            if type(specific_channel) == discord.TextChannel:
                vals.append((specific_channel.id,specific_channel.name,
                            specific_channel.topic,str(specific_channel.type),
                            specific_channel.is_nsfw(),
                            specific_channel.is_news(),
                            specific_channel.category_id))
            
            else:
                vals.append((specific_channel.id,specific_channel.name,"NULL",
                            str(specific_channel.type),False,False,
                            specific_channel.category_id))
        
        # Add each of the tuples to the database.
        try:
            cursor.executemany(sql,vals)

        except Exception as err:
            logger.critical(f"There was an error executing a command.\n{err}")

        mydb.commit()
    
    # Mention that there are no new channels to be added.
    else:
        logger.debug(f"No new channels have been added in \'{guild.name}\' "+
                     "since reawakening.")

    logger.info(f"Channel check in \'{guild.name}\' complete.")

def member_check(guild: discord.Guild):
    """
    Run when there's a need to check for new members.\n
    guild: The guild that the bot will get the members for.
    """
    logger.info(f"Checking the members in \'{guild.name}\'.")

    # Set up the cursor.
    cursor = ""
    
    try:
        cursor = mydb.cursor()
    
    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")

    # Instantiate a list for the member IDs.
    members_id = []
    
    # Get the member ID of each member within the specific guild.
    for member in guild.members:
        members_id.append(member.id)
    
    # Specify which database will be used.
    try:
        cursor.execute(f"USE server{guild.id}")
    
    except ProgrammingError as err:
        logger.critical(f"There was an issue connecting to the {guild.name} "+
                        f"database.\n{err}")
    
    # Execute the command to get all of the member IDs from that database.
    try:
        cursor.execute("SELECT * FROM Members")
        records = cursor.fetchall()
    
    except Exception as err:
        logger.critical("There was an issue making a selection from members."+
                        f"\n{err}")

    updated_members = []

    # Go through each record returned and remove it from the ID list if it
    # exists.
    for row in records:
        test_member = guild.get_member(row[0])

        if test_member:
            member_tuple = (test_member.id,test_member.name,
                            int(test_member.discriminator),int(test_member.bot),
                            test_member.nick)

            if member_tuple != row:
                updated_members.append((member_tuple[1],member_tuple[2],
                                    member_tuple[3],member_tuple[4],
                                    member_tuple[0]))

        if row[0] in members_id:
            members_id.remove(row[0])

    # Instantiate a list that will hold the actual members that are new.
    members = []

    # Go through each one and get the member information.
    for member in members_id:
        spec_member = guild.get_member(member)
        members.append((spec_member.id,spec_member.name,
                        spec_member.discriminator,spec_member.bot,
                        spec_member.nick))

    if len(updated_members) > 0:
        logger.info(f"{len(updated_members)} members have been updated in "+
                    f"\'{guild.name}\' since reawakening. Updating them now.")
        
        sql=("UPDATE Members SET memberName=%s,discriminator=%s,isBot=%s,"+
             "nickname=%s WHERE memberID=%s")

        cursor.executemany(sql,updated_members)
        mydb.commit()

    else:
        logger.debug(f"No members have been updated in \'{guild.name}\' since "+
                     "reawakening.")

    # If there are members to add to the database, add them.
    if len(members) > 0:
        logger.info(f"{len(members)} have joined \'{guild.name}\' since "+
                    "reawakening. Adding them now.")
        sql = ("INSERT INTO Members (memberID,memberName,discriminator,"+
                "isBot,nickname) VALUES (%s,%s,%s,%s,%s)")

        try:
            cursor.executemany(sql,members)

        except Exception as err:
            logger.critical(f"There was an error executing a command.\n{err}")

        mydb.commit()

    else:
        logger.debug(f"No new members have joined \'{guild.name}\' since "+
                    "reawakening.")

    cursor.close()
    logger.info("Member check complete.")

async def message_check(guild: discord.Guild, client: discord.Client):
    """
    Run when there's a need to check a guild's messages.\n
    guild: The guild that the bot will get the messages for.\n
    client: The bot client. Used to get any members that left the server that
    left messages.
    """
    logger.info(f"Checking for new messages in \'{guild.name}\'.")
    # Instantiate a list for the raw messages.
    raw_messages = []

    try:
        cursor = mydb.cursor()
    
    except OperationalError:
        logger.critical("The MySQL connection is unavailable.")

    # Specify which database to use.
    try:
        cursor.execute(f"USE server{guild.id}")
    
    except ProgrammingError as err:
        logger.critical(f"There was an issue accessing {guild.name}.\n{err}")

    # Go through each channel
    for channel in guild.channels:
        # Only worry about text channels.
        if type(channel) == discord.channel.TextChannel:
            raw_messages = (raw_messages +
                            await channel.history(limit=None).flatten())

    # Reverse the raw messages so they're in order from oldest to newest.
    raw_messages.reverse()

    # Get a list of messages that are already in the server.
    try:
        cursor.execute("SELECT messageID,hasAttachment,qualifiedName,message "+
                       "FROM Messages")
        records = cursor.fetchall()
    
    except Exception as err:
        logger.critical(f"There was an issue selecting messages.\n{err}")

    # Convert tuple'd records from SQL to simple list.
    message_list = []
    for row in records:
        if row[0] not in message_list:
            message_list.append(row[0]) 

    # Use that list to remove any messages that are already in the server
    # from the raw message list.
    clean_messages = []
    attachment_list = []
    message_ID_list = []
    deleted_messages = []
    edited_messages = []

    raw_users = []
    for mess in raw_messages:
        if not next((v for i,v in enumerate(records) if v[3]==mess.content),
                    None):
            edited_messages.append(mess)

        raw_users.append(mess.author.id)
        if mess.id not in message_list:
            clean_messages.append(mess)
        
        message_ID_list.append(mess.id)

        if mess.attachments:
            attachment_list.append(mess)

    for row in records:
        if row[0] not in message_ID_list:
            deleted_messages.append(row[0])

    sql = "SELECT memberID FROM Members"
    try:
        cursor.execute(sql)
        records = cursor.fetchall()
    
    except Exception as err:
        logger.critical(f"There was an issue selecting members.\n{err}")

    user_ID_list = []
    for row in records:
        user_ID_list.append(row[0])
    
    raw_users = list(dict.fromkeys(raw_users))

    for user in user_ID_list:
        if user in raw_users:
            raw_users.remove(user)
    
    sql = ("INSERT INTO Members (memberID,memberName,discriminator,isBot,"+
          "nickname) VALUES (%s,%s,%s,%s,%s)")
    vals = []
    for userID in raw_users:
        user = client.get_user(userID)
        vals.append((user.id,user.name,user.discriminator,user.bot,
                    user.display_name))
    
    try:
        cursor.executemany(sql,vals)

    except Exception as err:
        logger.critical(f"There was an error executing a command.\n{err}")

    mydb.commit()

    sql = "UPDATE Messages SET isDeleted=%s,dateDeleted=%s WHERE messageID=%s"
    vals = []
    for mess in deleted_messages:
        vals.append((True,datetime.utcnow().strftime(time_format),mess))

    try:
        cursor.executemany(sql,vals)

    except Exception as err:
        logger.critical(f"There was an error executing a command.\n{err}")

    mydb.commit()

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

    if len(edited_messages) > 0:
        logger.info(f"There have been {len(edited_messages)} messages edited "+
                    f"in \'{guild.name}\' since reawakening. Updating them "+
                    "now.")
        
        for message in edited_messages:
            edited_message(message)
            await new_message(message)

    else:
        logger.debug(f"No messages have been edited in \'{guild.name}\' since "+
                     "reawakening.")

    # If there are messages to add.
    if len(clean_messages) > 0:
        logger.info(f"There have been {len(clean_messages)} messages written "+
                    f"in \'{guild.name}\' since reawakening. Adding them now.")
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
    
    else:
        logger.debug("There have been no new messages posted in "+
                     f"\'{guild.name}\' since reawakening.")

    # If there are attachment messages to add to the database.
    if len(to_upload_attach) > 0:
        logger.debug(f"There are {len(to_upload_attach)} messages with "+
                     f"attachments to upload in \'{guild.name}\'.")
        sql = ("INSERT INTO Messages (messageID, channelID, authorID,"+
                "dateCreated, message, hasAttachment, attachmentID,"+
                "filename, qualifiedName, url) VALUES"+
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)")
        
        try:
            cursor.executemany(sql,to_upload_attach)

        except Exception as err:
            logger.critical(f"There was an error executing a command.\n{err}")

        mydb.commit()

    # If there are non-attachment messages to add to the database.
    if len(to_upload_no_attach) > 0:
        logger.debug(f"There are {len(to_upload_no_attach)} messages with no "+
                     f"attachments to upload in \'{guild.name}\'.")
        sql = ("INSERT INTO Messages (messageID, channelID, authorID,"+
                "dateCreated, message) VALUES (%s,%s,%s,%s,%s)")
        
        try:
            cursor.executemany(sql,to_upload_no_attach)

        except Exception as err:
            logger.critical(f"There was an error executing a command.\n{err}")

        mydb.commit()

    cursor.close()
    logger.info("Message check complete.")

def get_credentials(spec_database=None) -> MySQLConnection:
    """
    A helper function used to get the credentials for the server, simplifying
    the process.\n
    spec_database: The database that the bot is connecting to. By default is
    None due to the fact that the system is granular. Meaning multiple
    connections to multiple databases are possible making this option
    infeasible.
    """
    try:
        logger.info("Establishing a connection to the database server.")
        mydb=connect(
            host=config.get("database_credentials","address"),
            user=config.get("database_credentials","username"),
            password=config.get("database_credentials","password"))
        
        logger.info("Database server connection established.")
        return mydb

    # If the connection cannot be established due to input error, log and quit.
    except ProgrammingError:
        logger.critical("There was an error with the credentials. "+
                        "Shutting down.")
        exit()
    
    except InterfaceError:
        logger.critical("The database server cannot be accessed. "+
                        "Shutting down.")
        exit()
    
    except Exception as err:
        logger.critical(f"Connection failed due to unknown reason.\n{err}")
        exit()

# Create a new mydb connection to be used throughout the project.
mydb = get_credentials()
