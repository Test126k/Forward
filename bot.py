from pyrogram import Client, filters
from pyrogram.types import Message
from pymongo import MongoClient

# Initialize MongoDB
mongo_client = MongoClient("YOUR_MONGODB_URI")
db = mongo_client["telegram_bot_db"]
collection = db["user_data"]

# Initialize the bot
app = Client(
    "forward_bot",
    api_id="YOUR_API_ID",
    api_hash="YOUR_API_HASH",
    bot_token="YOUR_BOT_TOKEN"
)

# Start forwarding command handler
@app.on_message(filters.command("forward") & filters.private)
async def start_forwarding(client, message: Message):
    user_id = message.from_user.id
    # Save the initial state to MongoDB
    collection.update_one({"user_id": user_id}, {"$set": {"step": "awaiting_source_channel"}}, upsert=True)
    await message.reply("Please send me the source channel username or ID (e.g., `@source_channel`).")

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
        
        # Get source and destination channels from MongoDB
        source_channel = user_data["source_channel"]
        
        await message.reply(f"Starting to forward messages from {source_channel} to {destination_channel}...")
        
        # Forward messages from the source to the destination channel
        async for msg in client.get_chat_history(source_channel):
            try:
                await msg.forward(destination_channel)
            except Exception as e:
                print(f"Failed to forward message: {e}")
        
        # Reset state in MongoDB
        collection.update_one({"user_id": user_id}, {"$set": {"step": None}})
        await message.reply("Finished forwarding messages.")

# Run the bot
app.run()
