import discord

from sql_interface import (deleted_message, edited_message, new_message,
                           update_check, new_channel)

client = discord.Client()

@client.event
async def on_ready():
    # Inform the client that the login was successful.
    print(f'We have logged in as {client.user}')
    await update_check(client)
    print("Completed update check. Ready and waiting...")

@client.event
async def on_message(message: discord.Message):
    # Test to ensure that the client does not respond to itself.
    if message.author.bot:
        return

    # A call for the bot to quit.
    elif message.content.startswith('$quit'):
        print("Goodbye!")
        await message.channel.send('Quitting!')
        await client.logout()

    # Used after bot commands so as to not log them unnecessarily.
    else:        
        new_message(message)
        if message.attachments:
            await discord.Attachment.save(message.attachments[0],
                f"attachments/{message.attachments[0].id}"+
                f"{message.attachments[0].filename}")

    # Debug segment to discover how to get all of the old messages
    if message.content.startswith("$run"):
        messages = list(await message.channel.history(limit=None).flatten())
        messages.reverse()
        for mess in messages:
            print(f"{mess.content}")

@client.event
async def on_message_delete(message: discord.Message):
    # Note that a message was deleted.
    deleted_message(message)

@client.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    # Make note that the message was edited
    edited_message(before)

    # Add the edited message as a new one to ensure message integrity.
    new_message(after)

@client.event
async def on_guild_join(guild: discord.Guild):
    # TODO: Get a list of channels and download all of the messages/attachments.
    print(f"Joined: {guild.name} with ID {guild.id}")
    channels = guild.channels()
    # TODO: Create a new table based on the guild ID for the new guild.

@client.event
async def on_guild_channel_update(before: discord.TextChannel,
                                  after: discord.TextChannel):
    print(f"Before: {before}")
    print(f"After: {after}")

@client.event
async def on_guild_channel_create(channel: discord.TextChannel):
    new_channel(channel)

@client.event
async def on_guild_channel_delete(channel: discord.TextChannel):
    print(f"{channel.name} was deleted.")

# Run the client with the token.
with open("sensitive/bot_credentials", 'rt') as bot_credent:
    credent = bot_credent.read()
client.run(credent)

# https://discordpy.readthedocs.io/en/latest/index.html
