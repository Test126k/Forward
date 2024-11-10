import asyncio
from pyrogram import Client, filters
from pyrogram.errors import PeerIdInvalid, ChannelInvalid

# Replace with your own bot token and credentials
api_id = "YOUR_API_ID"
api_hash = "YOUR_API_HASH"
bot_token = "YOUR_BOT_TOKEN"

# Initialize the bot client
client = Client("forwarder", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Global flag to control forwarding and store user sessions
forwarding_active = {}
user_sessions = {}

async def get_channel_id(client, channel_identifier):
    """Helper function to resolve channel ID."""
    try:
        print(f"Attempting to resolve channel: {channel_identifier}")
        chat = await client.get_chat(channel_identifier)
        print(f"Resolved channel ID: {chat.id}")
        return chat.id
    except (PeerIdInvalid, ChannelInvalid) as e:
        print(f"Error resolving channel: {e}")
        return None

@client.on_message(filters.command("start"))
async def start(client, message):
    """Handle the /start command."""
    await message.reply("Welcome! Use /forward to start forwarding messages.")

@client.on_message(filters.command("forward"))
async def forward(client, message):
    """Initiate forwarding process and ask for source channel."""
    user_id = message.from_user.id
    
    if forwarding_active.get(user_id, False):
        await message.reply("You're already forwarding messages. Use /stop to stop.")
        return
    
    user_sessions[user_id] = {"step": "awaiting_source"}
    await message.reply("Please send the source channel (e.g., @channelusername or channel ID).")

@client.on_message(filters.text)
async def handle_response(client, message):
    """Handle responses for source and destination channels."""
    user_id = message.from_user.id
    
    # Check if the user is in a forwarding setup process
    if user_id in user_sessions:
        session = user_sessions[user_id]
        
        if session["step"] == "awaiting_source":
            # Store source channel and ask for destination
            session["source_channel"] = message.text.strip()
            session["step"] = "awaiting_destination"
            await message.reply("Now, send the destination channel (e.g., @channelusername or channel ID).")
        
        elif session["step"] == "awaiting_destination":
            # Store destination channel and start forwarding
            session["destination_channel"] = message.text.strip()
            source_channel = session["source_channel"]
            destination_channel = session["destination_channel"]

            # Resolve source and destination channel IDs
            source_channel_id = await get_channel_id(client, source_channel)
            if source_channel_id is None:
                await message.reply(f"Could not resolve source channel: {source_channel}. Please ensure the bot has access.")
                user_sessions.pop(user_id, None)
                return

            destination_channel_id = await get_channel_id(client, destination_channel)
            if destination_channel_id is None:
                await message.reply(f"Could not resolve destination channel: {destination_channel}. Please ensure the bot has access.")
                user_sessions.pop(user_id, None)
                return

            # Set flag and start forwarding
            forwarding_active[user_id] = True
            await message.reply(f"Starting to forward messages from {source_channel} to {destination_channel}...")

            # Perform the actual forwarding
            try:
                async for msg in client.get_chat_history(source_channel_id):
                    if not forwarding_active.get(user_id, False):
                        await message.reply("Forwarding has been stopped.")
                        break
                    
                    # Forward text, photos, videos, audio, and documents
                    if msg.text:
                        await client.send_message(destination_channel_id, msg.text)
                    elif msg.photo:
                        await client.send_photo(destination_channel_id, msg.photo.file_id, caption=msg.caption)
                    elif msg.video:
                        await client.send_video(destination_channel_id, msg.video.file_id, caption=msg.caption)
                    elif msg.audio:
                        await client.send_audio(destination_channel_id, msg.audio.file_id, caption=msg.caption)
                    elif msg.document:
                        await client.send_document(destination_channel_id, msg.document.file_id, caption=msg.caption)

                    await asyncio.sleep(1)  # To avoid hitting rate limits

            except Exception as e:
                await message.reply(f"An error occurred while forwarding messages: {str(e)}")
                print(f"Error: {e}")

            # Clean up session and reset
            user_sessions.pop(user_id, None)

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
