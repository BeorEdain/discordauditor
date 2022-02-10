import logging
import os

import discord
from discord.ext import commands

from sql_interface import (channel_check, command_gimme, delete_channel,
                           deleted_message, edited_message, guild_check,
                           guild_join, guild_leave, guild_update, logger,
                           member_check, member_join, member_update,
                           message_check, mydb, new_channel, new_message,
                           update_channel, user_update, voice_activity)

logger.info("Initializing discord bot.")

bot_prefix="$"
bot = commands.Bot(command_prefix=bot_prefix)
bot.owner_id = int(os.getenv('bot_owner'))

@bot.command(name="quit",help="Shuts the bot down. Only the bot owner can "+
             "use this.",hidden=True)
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

@bot.command(name="gimme",brief="Used to retrieve messages from a server.",
             help="Retrieves the specified information for a given user in a "+
             "specified server.",usage=f"<user/all> from <guild> <between> "+
             f"<date1> and <date2>\n{bot_prefix}gimme <user/all> from <guild> "+
             f"<before/after> <date>\n{bot_prefix}gimme <user/all> from "+
             "<guild> latest <number>\nAll dates must be in either the "+
             "YYYY/MM/DD or YYYY/MM/DD HH:MM:SS time formats. All times are "+
             "in UTC.")
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

bot.run(os.getenv('credentials'))
