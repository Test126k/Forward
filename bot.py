import asyncio
from pyrogram import Client, filters
from pyrogram.errors import PeerIdInvalid

# Replace with your own bot token
api_id = "YOUR_API_ID"
api_hash = "YOUR_API_HASH"
bot_token = "YOUR_BOT_TOKEN"

# Initialize the bot client
client = Client("forwarder", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Global flag to control forwarding
forwarding_active = {}

async def get_channel_id(client, channel_identifier):
    """Helper function to resolve channel ID."""
    try:
        print(f"Attempting to resolve channel: {channel_identifier}")

        # If the source is an invite link, the bot needs to join it first
        if "t.me/joinchat/" in channel_identifier:
            print(f"Attempting to join private channel using invite link: {channel_identifier}")
            await client.join_chat(channel_identifier)  # Bot joins the channel
            chat = await client.get_chat(channel_identifier)  # Get chat details after joining
            print(f"Joined channel, resolved ID: {chat.id}")
        else:
            # Resolving a public or already accessible private channel
            print(f"Resolving public/private channel: {channel_identifier}")
            chat = await client.get_chat(channel_identifier)
            print(f"Resolved channel ID: {chat.id}")
        
        return chat.id
    except Exception as e:
        print(f"Error resolving channel: {e}")
        return None

@client.on_message(filters.command("start"))
async def start(client, message):
    """Handle the /start command."""
    await message.reply("Welcome! Use /forward to start forwarding messages.")

@client.on_message(filters.command("forward"))
async def forward(client, message):
    """Handle the /forward command to start forwarding messages."""
    user_id = message.from_user.id
    
    # Ensure the bot is not already forwarding
    if forwarding_active.get(user_id, False):
        await message.reply("You're already forwarding messages. Use /stop to stop.")
        return
    
    # Ask the user for the source and destination channel
    await message.reply("Please send the source channel (e.g., @channelusername or channel ID).")
    source_msg = await client.listen(message.chat.id)
    source_channel = source_msg.text.strip()

    await message.reply("Now, send the destination channel (e.g., @channelusername or channel ID).")
    dest_msg = await client.listen(message.chat.id)
    destination_channel = dest_msg.text.strip()

    # Resolve source and destination channels
    source_channel_id = await get_channel_id(client, source_channel)
    if source_channel_id is None:
        await message.reply(f"Could not resolve source channel: {source_channel}. Please ensure the bot has access.")
        return

    destination_channel_id = await get_channel_id(client, destination_channel)
    if destination_channel_id is None:
        await message.reply(f"Could not resolve destination channel: {destination_channel}. Please ensure the bot has access.")
        return

    # Set the flag to start forwarding
    forwarding_active[user_id] = True
    await message.reply(f"Starting to forward messages from {source_channel} to {destination_channel}...")

    try:
        # Forward messages from the source channel to the destination channel
        async for msg in client.get_chat_history(source_channel_id):
            if not forwarding_active.get(user_id, False):
                await message.reply("Forwarding has been stopped.")
                break

            # Forward text messages
            if msg.text:
                await client.send_message(destination_channel_id, msg.text)
            # Forward photos
            elif msg.photo:
                await client.send_photo(destination_channel_id, msg.photo)
            # Forward videos
            elif msg.video:
                await client.send_video(destination_channel_id, msg.video)
            # Forward audio
            elif msg.audio:
                await client.send_audio(destination_channel_id, msg.audio)
            # Forward documents
            elif msg.document:
                await client.send_document(destination_channel_id, msg.document)

            # Delay between forwards to avoid hitting rate limits
            await asyncio.sleep(1)  # Adjust as necessary to avoid rate limits

    except PeerIdInvalid as e:
        await message.reply(f"Error: {str(e)}. Please make sure the bot has access to the channels.")
    except Exception as e:
        await message.reply(f"An error occurred while forwarding messages: {str(e)}")
        print(f"Error: {e}")

@client.on_message(filters.command("stop"))
async def stop_forwarding(client, message):
    """Handle the /stop command to stop forwarding messages."""
    user_id = message.from_user.id

    if forwarding_active.get(user_id, False):
        forwarding_active[user_id] = False
        await message.reply("Forwarding has been stopped.")
    else:
        await message.reply("You're not currently forwarding any messages.")

# Run the client
client.run()
