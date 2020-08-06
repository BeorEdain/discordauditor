# discordauditor

The idea behind this bot is to have a persistent watcher in a server that will
log everything that is sent in it and save a copy of each thing. This is useful
for any time there is contention within a server regarding what was or wasn't
said and by whom.

What the bot logs:
1. What was written in a message.
2. If a message was edited, what it was prior and what it was edited to.
3. If a message was deleted, and by whom it was deleted.
4. Any attachments that were uploaded to the server.
