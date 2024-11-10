import asyncio
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.errors import PeerIdInvalid, ChannelInvalid

# Replace with your own bot token and credentials
api_id = "26300022"
api_hash = "def44e13defba9d104323e821955dfa3"
bot_token = "7207796438:AAEAeEf3DWK5qEVOzihkmGw4E4SmYYWpnx8"

# MongoDB setup
MONGODB_URI = "YOUR_MONGODB_URI"
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["telegram_bot_db"]
sessions_collection = db["user_sessions"]

# Initialize the bot client
client = Client("forwarder", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

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
    await message.reply("Welcome! Use /forward to start forwarding messages.")

@client.on_message(filters.command("forward"))
async def forward(client, message):
    user_id = message.from_user.id
    session = sessions_collection.find_one({"user_id": user_id})

    if session and session.get("forwarding_active"):
        await message.reply("You're already forwarding messages. Use /stop to stop.")
        return

    sessions_collection.update_one(
        {"user_id": user_id},
        {"$set": {"step": "awaiting_source", "forwarding_active": False}},
        upsert=True
    )
    await message.reply("Please send the source channel (e.g., @channelusername or channel ID).")

@client.on_message(filters.text)
async def handle_response(client, message):
    user_id = message.from_user.id
    session = sessions_collection.find_one({"user_id": user_id})

    if session:
        step = session.get("step")

        if step == "awaiting_source":
            sessions_collection.update_one(
                {"user_id": user_id},
                {"$set": {"source_channel": message.text.strip(), "step": "awaiting_destination"}}
            )
            await message.reply("Now, send the destination channel (e.g., @channelusername or channel ID).")

        elif step == "awaiting_destination":
            sessions_collection.update_one(
                {"user_id": user_id},
                {"$set": {"destination_channel": message.text.strip(), "step": "ready_to_forward", "forwarding_active": True}}
            )
            await start_forwarding(client, message)

async def start_forwarding(client, message):
    user_id = message.from_user.id
    session = sessions_collection.find_one({"user_id": user_id})
    source_channel = session["source_channel"]
    destination_channel = session["destination_channel"]

    source_channel_id = await get_channel_id(client, source_channel)
    destination_channel_id = await get_channel_id(client, destination_channel)

    if not source_channel_id or not destination_channel_id:
        await message.reply("Could not resolve one of the channels. Please check access.")
        return

    try:
        await message.reply(f"Starting to forward messages from {source_channel} to {destination_channel}...")

        async for msg in client.get_chat_history(source_channel_id):
            if not sessions_collection.find_one({"user_id": user_id, "forwarding_active": True}):
                await message.reply("Forwarding has been stopped.")
                break

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

            await asyncio.sleep(1)

    except Exception as e:
        await message.reply(f"An error occurred: {str(e)}")

@client.on_message(filters.command("stop"))
async def stop_forwarding(client, message):
    user_id = message.from_user.id
    sessions_collection.update_one({"user_id": user_id}, {"$set": {"forwarding_active": False}})
    await message.reply("Forwarding has been stopped.")

client.run()
