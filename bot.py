import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

# Fetch environment variables
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
mongo_uri = os.getenv("MONGODB_URI")

# Initialize MongoDB
mongo_client = MongoClient(mongo_uri)
db = mongo_client["telegram_bot_db"]
collection = db["user_data"]

# Initialize the bot
app = Client(
    "forward_bot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token
)

# Start a simple HTTP server for health checks on port 8080
def start_health_check_server():
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    httpd.serve_forever()

# Start HTTP server in a separate thread
threading.Thread(target=start_health_check_server, daemon=True).start()

# Global flag to control the forwarding process
forwarding_active = {}

# Start forwarding command handler
@app.on_message(filters.command("forward") & filters.private)
async def start_forwarding(client, message: Message):
    user_id = message.from_user.id
    # Save the initial state to MongoDB
    collection.update_one({"user_id": user_id}, {"$set": {"step": "awaiting_source_channel"}}, upsert=True)
    await message.reply("Please send me the source channel username or ID (e.g., `@source_channel`).")

# Stop forwarding command handler
@app.on_message(filters.command("stop") & filters.private)
async def stop_forwarding(client, message: Message):
    user_id = message.from_user.id
    forwarding_active[user_id] = False  # Set the forwarding flag to False
    await message.reply("Forwarding process has been stopped.")

# Text message handler to process user responses
@app.on_message(filters.private & filters.text)
async def handle_response(client, message: Message):
    user_id = message.from_user.id
    user_data = collection.find_one({"user_id": user_id})
    
    if not user_data:
        return
    
    # Check the current step
    step = user_data.get("step")
    
    if step == "awaiting_source_channel":
        source_channel = message.text.strip()
        collection.update_one({"user_id": user_id}, {"$set": {"source_channel": source_channel, "step": "awaiting_destination_channel"}})
        await message.reply("Got it! Now send me the destination channel username or ID (e.g., `@destination_channel`).")
    
    elif step == "awaiting_destination_channel":
        destination_channel = message.text.strip()
        collection.update_one({"user_id": user_id}, {"$set": {"destination_channel": destination_channel, "step": "forwarding_messages"}})
        
        # Set forwarding as active for this user
        forwarding_active[user_id] = True

        # Get source and destination channels from MongoDB
        source_channel = user_data["source_channel"]
        
        await message.reply(f"Starting to forward messages from {source_channel} to {destination_channel}...")

        # Forward messages from the source to the destination channel
        try:
            # If source_channel is an invite link, join the chat
            if "t.me/joinchat/" in source_channel:
                await client.join_chat(source_channel)
                source_channel = (await client.get_chat(source_channel)).id  # Get the actual chat ID after joining
            
            # Fetch messages from the source channel
            async for msg in client.get_chat_history(source_channel):
                # Stop forwarding if the user sent the /stop command
                if not forwarding_active.get(user_id, False):
                    await message.reply("Forwarding has been stopped.")
                    break
                
                # Debugging: Log each message to see if it’s fetched correctly
                print(f"Fetched message ID: {msg.message_id} | Date: {msg.date} | Type: {msg.media or 'text'}")

                # Forward all messages using copy
                await msg.copy(destination_channel)
        except Exception as e:
            print(f"Error fetching messages: {e}")
            await message.reply(f"Error: {e}")
        
        # Reset state in MongoDB
        collection.update_one({"user_id": user_id}, {"$set": {"step": None}})
        await message.reply("Finished forwarding messages.")

# Run the bot
app.run()
