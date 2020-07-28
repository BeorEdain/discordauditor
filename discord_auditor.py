import discord

client = discord.Client()

@client.event
async def on_ready():
    # Inform the client that the login was successful
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    # Test to ensure that the client does not respond to itself
    if message.author == client.user:
        return
    
    # A call for the bot to quit
    if message.content.startswith('$quit'):
        await message.channel.send('Quitting!')
        await client.logout()

    # A simple test to ensure the bot is working
    if message.content.startswith('$test'):
        await message.channel.send('Testing!')

    # Print the author, message, and channel
    print(f"{message.author} posted \"{message.content}\" " +
          f"in the {message.channel} channel")

    # Print if there are any attachments and also save them
    if message.attachments:
        print(f"Attachments: {message.attachments}")
        await discord.Attachment.save(message.attachments[0],
              f"attachments/{message.attachments[0].filename}")

@client.event
async def on_message_delete(message):
    # Note that a message was deleted
    print(f"This message was deleted: {message}")

@client.event
async def on_message_edit(before, after):
    # Note that a message was edited
    print(f"Before: {before.content}")
    print(f"After: {after.content}")

# Run the client with the token
with open("sensitive/bot_credentials", 'rt') as bot_credent:
    credent = bot_credent.read()
client.run(credent)

# https://discordpy.readthedocs.io/en/latest/index.html