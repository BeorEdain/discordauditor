import logging
import os
from getpass import getpass
from random import choice

import discord

from sql_interface import (channel_check, delete_channel, deleted_message,
                           edited_message, guild_check, guild_join,
                           guild_leave, logger, member_check, message_check,
                           new_channel, new_message, update_channel,
                           update_guild, voice_activity)

logger.info("Initializing discord client.")
client = discord.Client()

client_info = ""

@client.event
async def on_ready():
    global client_info
    logger.debug("Getting application info.")
    client_info = await client.application_info()
    # Inform the client that the login was successful.
    logger.info(f'We have logged in as {client.user}.')

    # Check for any new guilds since the bot had been restarted.
    guild_check(client)

    for guild in client.guilds:
        # Check for any new channels within the enrolled guilds since the bot
        # was restarted.
        channel_check(guild)

        # Check for any new members within the enrolled guilds since the bot was
        # restarted.
        member_check(guild)

        # Check for any new messages within the enrolled guilds since the bot
        # was restarted.
        await message_check(guild, client)

    # Inform the client that the updates completed and that the bot is waiting.
    logger.info("Update complete. Waiting.")

@client.event
async def on_message(message: discord.Message):
    if message.author.id == client.user.id:
        return

    # A call for the bot to quit.
    if (message.content.startswith('$quit') and 
                                message.author.id == client_info.owner.id):
        logger.info("Bot was told to close by owner. Shutting down.")
        print("Goodbye!")
        await message.channel.send('Quitting!')
        await client.logout()
    
    elif (message.content.startswith('$quit') and
                                message.author.id != client_info.owner.id):  
        possible_messages = ["You don't have enough badges to train me!",
                             "Nice try, punk.",
                             "You're not my master.",
                             "No.",
                             "You're not the boss of me.",
                             "Only the creator can shut me down.",
                             "I'm sorry Dave, I'm afraid I can't do that.",
                             "Stop it, that tickles.",
                             "UwU what's this?",
                             "Say '$quit' again. I dare you. I double dare you.",
                             "I can't rest when there are enemies nearby.",
                             "No U.",
                             "But I'm not tired!",
                             "Fight me.",
                             "You expected this to be the $quit command? Too "+
                             "bad! It was me, Dio!"]

        await message.channel.send(choice(possible_messages))

    else:
        await new_message(message)

@client.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    # Make note that the message was edited
    edited_message(before)

    # Add the edited message as a new one to ensure message integrity.
    await new_message(after)

@client.event
async def on_message_delete(message: discord.Message):
    # Note that a message was deleted.
    deleted_message(message)

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
    await guild_join(guild, client)

@client.event
async def on_guild_update(before: discord.Guild, after: discord.Guild):
    # If the name of the guild is changed make note of it.
    update_guild(after)

@client.event
async def on_guild_remove(guild: discord.Guild):
    # Note if a guild is left for whatever reason.
    guild_leave(guild)

##### BEGIN FILE EXISTANCE CHECKS ##############################################
# Write the information to a file so this does not need to happen again.
if not os.path.isdir("sensitive/"):
    logger.critical("sensitive/ does not exist. Creating.")
    os.mkdir("sensitive/")

if not os.path.isfile("sensitive/database_credentials"):
    logger.critical("database_credentials does not exist, polling client.")
    # Notify client that the database_credentials file could not be found.
    print("The database_credentials file does not exist")

    # Get the IP address or hostname of the MySQL server.
    ip=input("Please enter the IP address or hostname of the database server:")

    # Get the username that will be used for all MySQL transactions.
    user=input("Please enter the username that is used to log in:")

    # Get the password for the aforementioned user in a safe way.
    password=getpass(prompt=f"Please enter the password for {user}:")

    logger.info("Writing database_credentials to file.")        
    with open("sensitive/database_credentials", 'wt') as data_credent:
        data_credent.write(ip + "\n")
        data_credent.write(user + "\n")
        data_credent.write(password)
    
    # Blank the password just in case of leakage.
    password = ""

# Run the client with the token.
try:
    # Try to see if the bot_credentials file exists.
    with open("sensitive/bot_credentials", 'rt') as bot_credent:
        logger.info("Opening bot_credentials.")
        credent = bot_credent.read()

except FileNotFoundError:
    # If it does not, notify the client.
    logger.warning("bot_credentials does not exist. Polling user.")

    # Ask the client to provide a token for the bot.
    token = input("Please enter the bot token:")

    # Write the aforementioned token to a file so this does not need to happen
    # each time.
    logger.info("Writing bot_credentials to file.")
    with open("sensitive/bot_credentials", 'wt') as bot_credent:
        bot_credent.write(token)

client.run(credent)
        
# https://discordpy.readthedocs.io/en/latest/index.html
