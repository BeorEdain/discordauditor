import configparser
import logging
import os
from getpass import getpass
from random import choice

import discord
from discord.ext import commands

from sql_interface import (channel_check, command_gimme, delete_channel,
                           deleted_message, edited_message, guild_check,
                           guild_join, guild_leave, guild_update, logger,
                           member_check, member_join, member_update,
                           message_check, mydb, new_channel, new_message,
                           update_channel, user_update, voice_activity)

logger.info("Initializing discord bot.")

config = configparser.ConfigParser()

try:
    config.read_file(open(r'config.ini'))

except FileNotFoundError:
    print("config.ini does not exist. Creating now.")

    # Add [logger] section.
    config.add_section("logger")

    # Specify the log file type.
    log_file_type=input("What type of file do you want the log output to be?: ")
    config.set("logger","log_file_type",log_file_type)

    # Specify the log file name.
    log_filename=input("What would you like to name the log? ")
    config.set("logger","log_filename",log_filename)

    # Specify the log level.
    log_level="NULL"
    while log_level.lower() not in {"debug","info","warning","error",
                                    "critical"}:
        log_level=input("What level would you like the log to record"+
                        ",DEBUG, INFO, WARNING, ERROR, or CRITICAL?: ")
        config.set("logger","log_level",log_level.upper())

    # Specify the log save location.
    log_path=input("Where do you want the log files to be stored?: ")
    config.set("logger","log_path",log_path)

    # Specify whether the log should output to the console as well as the file.
    log_term_output=input("Do you want the bot to output the log to the "+
                          "console as well as to a file? Y/N: ")
    while log_term_output.lower() not in {"y","n"}:
        log_term_output=input("Please enter \"Y\" or \"N\": ")
    if log_term_output.lower() == "y":
        log_term_output = True
    else:
        log_term_output = False
    config.set("logger","log_term_output",log_term_output)

    # Add [bot] section.
    config.add_section("bot")

    # specify the bot owner.
    bot_owner=getpass("Please enter the unique ID of the bot owner. (It will "+
                      "appear blank. This is intended): ")
    config.set("bot","bot_owner",bot_owner)

    # Specify the bot command prefix.
    command_prefix=input("What symbol would you like to use for the command "+
                         "prefix?: ")
    config.set("bot","command_prefix",command_prefix)
    
    # Specify the bot credentials.
    credentials=getpass("Please enter the token for the bot to use. (It will "+
                        "appear blank. This is intended): ")
    config.set("bot","credentials",credentials)

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
    bot_owner=""
    credentials=""
    password=""

bot_prefix=config.get("bot","command_prefix")
bot = commands.Bot(command_prefix=bot_prefix)
bot.owner_id = int(config.get("bot","bot_owner"))

@bot.command(name="quit",help="Shuts the bot down.")
@commands.dm_only()
@commands.is_owner()
async def quit(ctx: commands.Context):
    # If the command came from the owner's guild and it was from the owner.
    logger.info("Bot was told to close by owner. Shutting down.")
    await ctx.send('Quitting!')
    await bot.logout()
    mydb.close()

@bot.command(name="leave",help="Used by guild owners to remove the bot from "+
             "their guild.")
async def leave(ctx: commands.Context):
    # A call for the bot to leave a guild.
    # If the message came from the guild owner.
    if ctx.author.id==ctx.guild.owner.id:
        await ctx.guild.leave()

@bot.command(name="gimme",help="Used to retrieve information.")
@commands.dm_only()
async def gimme(ctx: commands.Context, *args: str):
    request = ()

    if len(args)==7:
        request = (args[0],args[2],args[3],args[4],args[6])
        await command_gimme(ctx,request)
    elif len(args)==5:
        request = (args[0],args[2],args[3],args[4])
        await command_gimme(ctx,request)
    elif len(args)==4:
        request = (args[0],args[2],args[3])
        await command_gimme(ctx,request)
    else:
        await ctx.send(f"That command was invalid, please type {bot_prefix}"+
                      "gimme help for more information and proper formatting.")
    
@bot.event
async def on_ready():
    # Inform the bot that the login was successful.
    logger.info(f'bot is logged in as {bot.user}.')

    # Check for any new guilds since the bot had been restarted.
    guild_check(bot)

    for guild in bot.guilds:
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

    # Inform the log that the updates completed and that the bot is waiting.
    logger.info("Update complete. Waiting.")

@bot.event
async def on_message(message: discord.Message):
    # Unless the message is in a DM, save the message.
    if str(message.channel.type)!="private":
        await new_message(message)

    # If the message is from the bot, don't bother looking for a bot command.
    if message.author.id!=bot.user.id:
        await bot.process_commands(message)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    # Make note that the message was edited.
    edited_message(after)

    # Add the edited message as a new one to ensure message integrity.
    await new_message(after)

@bot.event
async def on_message_delete(message: discord.Message):
    # Note that a message was deleted.
    deleted_message(message)

@bot.event
async def on_member_join(member: discord.Member):
    # Add the new member to the Members table.
    member_join(member)

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    # If the user's nickname is changed, update the member in the table.
    if before.nick != after.nick:
        member_update(before, after)

@bot.event
async def on_user_update(before: discord.User, after: discord.User):
    # If the user's name or discriminator changes, update them in the table.
    if before.name != after.name or before.discriminator != after.discriminator:
        user_update(before, after)

@bot.event
async def on_voice_state_update(member: discord.Member,
                                before: discord.VoiceState,
                                after: discord.VoiceState):
    # Since we only care about who was in what channel and when, we only look to
    # see if the channels before and after are different.
    if before.channel != after.channel:
        voice_activity(member, before, after)

@bot.event
async def on_guild_channel_create(channel: discord.TextChannel):
    # Add a new channel to the guild.
    new_channel(channel)

@bot.event
async def on_guild_channel_update(before: discord.TextChannel,
                                  after: discord.TextChannel):
    # Update the channel.
    update_channel(after)

@bot.event
async def on_guild_channel_delete(channel: discord.TextChannel):
    # Mark a channel as deleted.
    delete_channel(channel)

@bot.event
async def on_guild_join(guild: discord.Guild):
    # Run the entire process to set up a new guild database and add it to the
    # primary guild database.
    await guild_join(guild)

@bot.event
async def on_guild_update(before: discord.Guild, after: discord.Guild):
    # If the name of the guild is changed make note of it.
    guild_update(after)

@bot.event
async def on_guild_remove(guild: discord.Guild):
    # Note if a guild is left for whatever reason.
    guild_leave(guild)

bot.run(config.get("bot","credentials"))
