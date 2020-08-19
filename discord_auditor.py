import configparser
import logging
import os
from getpass import getpass
from random import choice

import discord

from sql_interface import (channel_check, delete_channel, deleted_message,
                           edited_message, guild_check, guild_join,
                           guild_leave, guild_update, logger, member_check,
                           member_join, member_update, message_check,
                           new_channel, new_message, update_channel,
                           user_update, voice_activity)

logger.info("Initializing discord client.")
client = discord.Client()

client_info = ""

config = configparser.ConfigParser()

@client.event
async def on_ready():
    # Inform the client that the login was successful.
    logger.info(f'Client is logged in as {client.user}.')

    global client_info

    logger.debug("Getting application info.")
    client_info = await client.application_info()

    # Check for any new guilds since the bot had been restarted.
    guild_check(client)

    for guild in client.guilds:
        logger.info(f"Checking the \'{guild.name}\' guild.")
        # Check for any new channels within the enrolled guilds since the bot
        # was restarted.
        channel_check(guild)

        # Check for any new members within the enrolled guilds since the bot was
        # restarted.
        member_check(guild)

        # Check for any new messages within the enrolled guilds since the bot
        # was restarted.
        await message_check(guild)

        logger.info(f"Guild check of \'{guild.name}\' complete.")

    # Inform the client that the updates completed and that the bot is waiting.
    logger.info("Update complete. Waiting.")

@client.event
async def on_message(message: discord.Message):
    # If the message came from the bot itself, ignore it.
    if message.author.id==client.user.id:
        return
    
    if message.content!="$quit":
        await new_message(message)

    # If the message is for the bot to quit but doesn't come from the owner but
    # it is from one of the owner's guilds.
    elif (message.content=='$quit' and message.author.id!=client_info.owner.id
          and client_info.owner.id==message.guild.owner.id):
        possible_messages = []
        
        with open("possible_messages.txt", 'rt') as quips:
            for line in quips:
                possible_messages.append(line)

        await message.channel.send(choice(possible_messages))
        await new_message(message)

    elif (message.content=='$quit' and message.author.id==client_info.owner.id
          and message.guild.owner.id==client_info.owner.id):
        logger.info("Bot was told to close by owner. Shutting down.")
        await message.channel.send('Quitting!')
        await client.logout()

    # A call for the bot to leave a guild.
    # If the message came from the guild owner.
    elif (message.author.id==message.guild.owner.id and
          message.content=="$leave"):
        await message.guild.leave()

@client.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    # Make note that the message was edited.
    edited_message(after)

    # Add the edited message as a new one to ensure message integrity.
    await new_message(after)

@client.event
async def on_message_delete(message: discord.Message):
    # Note that a message was deleted.
    deleted_message(message)

@client.event
async def on_member_join(member: discord.Member):
    # Add the new member to the Members table.
    member_join(member)

@client.event
async def on_member_update(before: discord.Member, after: discord.Member):
    # If the user's nickname is changed, update the member in the table.
    if before.nick != after.nick:
        member_update(before, after)

@client.event
async def on_user_update(before: discord.User, after: discord.User):
    # If the user's name or discriminator changes, update them in the table.
    if before.name != after.name or before.discriminator != after.discriminator:
        user_update(before, after)

@client.event
async def on_voice_state_update(member: discord.Member,
                                before: discord.VoiceState,
                                after: discord.VoiceState):
    # Since we only care about who was in what channel and when, we only look to
    # see if the channels before and after are different.
    if before.channel != after.channel:
        voice_activity(member, before, after)

@client.event
async def on_guild_channel_create(channel: discord.TextChannel):
    # Add a new channel to the guild.
    new_channel(channel)

@client.event
async def on_guild_channel_update(before: discord.TextChannel,
                                  after: discord.TextChannel):
    # Update the channel.
    update_channel(after)

@client.event
async def on_guild_channel_delete(channel: discord.TextChannel):
    # Mark a channel as deleted.
    delete_channel(channel)

@client.event
async def on_guild_join(guild: discord.Guild):
    # Run the entire process to set up a new guild database and add it to the
    # primary guild database.
    await guild_join(guild)

@client.event
async def on_guild_update(before: discord.Guild, after: discord.Guild):
    # If the name of the guild is changed make note of it.
    guild_update(after)

@client.event
async def on_guild_remove(guild: discord.Guild):
    # Note if a guild is left for whatever reason.
    guild_leave(guild)

try:
    config.read_file(open(r'config.ini'))

except FileNotFoundError:
    print("config.ini does not exist. Creating now.")

    # Add [logger] section.
    config.add_section("logger")

    log_filename=input("What would you like to name the log? ")
    config.set("logger","log_filename",log_filename)

    # TODO: Create check to ensure it's one of the appropriate levels.
    log_level="NULL"
    while log_level.lower() not in {"debug","info","warning","error",
                                    "critical"}:
        log_level=input("What level would you like the log to record"+
                        ",DEBUG, INFO, WARNING, ERROR, or CRITICAL? ")
        config.set("logger","log_level",log_level.upper())

    log_term_output=input("Do you want the bot to output the log to the "+
                          "console as well as to a file? Y/N: ")
    
    while log_term_output.lower() not in {"y","n"}:
        log_term_output=input("Please enter \"Y\" or \"N\": ")

    if log_term_output.lower() == "y":
        log_term_output = True

    else:
        log_term_output = False

    config.set("logger","log_term_output",log_term_output)

    # Add [bot_credentials] section.
    config.add_section("bot_credentials")
    
    credentials=getpass("Please enter the token for the bot to use. (It will +"
                        "appear blank. This is intended): ")
    config.set("bot_credentials","credentials",credentials)

    # Add [database_credentials] section.
    config.add_section("database_credentials")

    address=input("Please enter the IP address or hostname of the database "+
                  "server: ")
    config.set("database_credentials","address",address)

    username=input("Please enter the username that can access this database: ")
    config.set("database_credentials","username",username)

    password=getpass(f"Please enter the password for user {username} (It will "+
                     "appear blank. This is intended): ")
    config.set("database_credentials","password",password)

    # Add [attach_path] section.
    config.add_section("attach_path")
    
    attach_path=input("Where do you want attachments to be saved? ")
    config.set("attach_path","path",attach_path)

    with open('config.ini','wt') as config_file:
        config.write(config_file)
    
    config.read_file(open(r'config.ini'))

    # Blank credentials and password in case of leakage.
    credentials=""
    password=""

client.run(config.get("bot_credentials","credentials"))
