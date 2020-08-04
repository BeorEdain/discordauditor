import discord

from sql_interface import (delete_channel, deleted_message, edited_message,
                           guild_join, new_channel, new_message,
                           update_channel, update_check, update_guild)

client = discord.Client()

@client.event
async def on_ready():
    # Inform the client that the login was successful.
    print(f'We have logged in as {client.user}')
    await update_check(client)
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
async def on_message_delete(message: discord.Message):
    # Note that a message was deleted.
    deleted_message(message)

@client.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    # Make note that the message was edited
    edited_message(before)

    # Add the edited message as a new one to ensure message integrity.
    await new_message(after)

@client.event
async def on_guild_join(guild: discord.Guild):
    guild_join(guild)

@client.event
async def on_guild_channel_update(before: discord.TextChannel,
                                  after: discord.TextChannel):
    update_channel(after)

@client.event
async def on_guild_channel_create(channel: discord.TextChannel):
    new_channel(channel)

@client.event
async def on_guild_channel_delete(channel: discord.TextChannel):
    print(f"{channel.name} was deleted.")
    delete_channel(channel)

@client.event
async def on_guild_update(before: discord.Guild, after: discord.Guild):
    if before.name != after.name:
        update_guild(after)

# Run the client with the token.
with open("sensitive/bot_credentials", 'rt') as bot_credent:
    credent = bot_credent.read()
client.run(credent)

# https://discordpy.readthedocs.io/en/latest/index.html
