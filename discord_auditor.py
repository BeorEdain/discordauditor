# TODO: Create actual logging. Like with a logger.

import os
from getpass import getpass

import discord

from sql_interface import (channel_check, delete_channel, deleted_message,
                           edited_message, guild_check, guild_join,
                           guild_leave, member_check, message_check,
                           new_channel, new_message, update_channel,
                           update_guild)

client = discord.Client()

@client.event
async def on_ready():
    # Inform the client that the login was successful.
    print(f'We have logged in as {client.user}')

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
        await message_check(guild)

    # Inform the client that the updates completed and that the bot is waiting.
    print("Completed update check. Ready and waiting...")

@client.event
async def on_message(message: discord.Message):
    # A call for the bot to quit.
    if message.content.startswith('$quit'):
        print("Goodbye!")
        await message.channel.send('Quitting!')
        await client.logout()

    # Used after bot commands so as to not log them unnecessarily.
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
    if before.name != after.name:
        update_guild(after)

@client.event
async def on_guild_remove(guild):
    # Note if a guild is left for whatever reason.
    guild_leave(guild)

##### BEGIN FILE EXISTANCE CHECKS ##############################################
if not os.path.isfile("sensitive/database_credentials"):
    # Notify client that the database_credentials file could not be found.
    print("The database_credentials file doesn't exist")

    # Get the IP address or hostname of the MySQL server.
    ip=input("Please enter the IP address or hostname of the database server:")

    # Get the username that will be used for all MySQL transactions.
    user=input("Please enter the username that is used to log in:")

    # Get the password for the aforementioned user in a safe way.
    password=getpass(prompt=f"Please enter the password for {user}:")

    # Write the information to a file so this doesn't need to happen again.
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
        credent = bot_credent.read()
        client.run(credent)

except FileNotFoundError:
    # If it doesn't, notify the client.
    print("Could not find the bot_credentials file")

    # Ask the client to provide a token for the bot.
    token = input("Please enter the bot token:")

    # Write the aforementioned token to a file so this doesn't need to happen
    # each time.
    with open("sensitive/bot_credentials", 'wt') as bot_credent:
        bot_credent.write(token)
        
# https://discordpy.readthedocs.io/en/latest/index.html
