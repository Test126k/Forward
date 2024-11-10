import asyncio
from pyrogram import Client, filters
from pyrogram.errors import PeerIdInvalid, ChannelInvalid, BotMethodInvalid
from aiohttp import web

# Replace with your API credentials
api_id = "26300022"
api_hash = "def44e13defba9d104323e821955dfa3"
bot_token = "7207796438:AAEAeEf3DWK5qEVOzihkmGw4E4SmYYWpnx8"

client = Client("forwarder_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Track whether forwarding is active
forwarding_active = False
source_channel = None
destination_channel = None

async def get_channel_id(client, channel_identifier):
    """Helper to resolve channel ID."""
    try:
        chat = await client.get_chat(channel_identifier)
        return chat.id
    except (PeerIdInvalid, ChannelInvalid) as e:
        print(f"Error resolving channel: {e}")
        return None

@client.on_message(filters.command("start"))
async def start(client, message):
    await message.reply("Welcome! Use /forward to start forwarding messages and /stop to stop.")

@client.on_message(filters.command("forward"))
async def start_forwarding(client, message):
    global forwarding_active, source_channel, destination_channel

    if forwarding_active:
        await message.reply("Already forwarding messages. Use /stop to stop.")
        return

    # Prompt for source and destination channels
    await message.reply("Send me the source channel (e.g., @channelusername or channel ID):")
    source_response = await client.listen(message.chat.id)
    source_channel = source_response.text.strip()

    await message.reply("Send me the destination channel (e.g., @channelusername or channel ID):")
    destination_response = await client.listen(message.chat.id)
    destination_channel = destination_response.text.strip()

    # Resolve channels
    source_channel_id = await get_channel_id(client, source_channel)
    destination_channel_id = await get_channel_id(client, destination_channel)

    if not source_channel_id or not destination_channel_id:
        await message.reply("Could not resolve one of the channels. Please check access.")
        return

    forwarding_active = True
    await message.reply(f"Starting to forward messages from {source_channel} to {destination_channel}...")

    try:
        async for msg in client.get_chat_history(source_channel_id):
            if not forwarding_active:
                await message.reply("Forwarding has been stopped.")
                break

            # Forward different message types
            if msg.text:
                await client.send_message(destination_channel_id, msg.text)
            elif msg.photo:
                await client.send_photo(destination_channel_id, msg.photo.file_id, caption=msg.caption)
            elif msg.video:
                await client.send_video(destination_channel_id, msg.video.file_id, caption=msg.caption)
            elif msg.document:
                await client.send_document(destination_channel_id, msg.document.file_id, caption=msg.caption)
            
            await asyncio.sleep(1)  # Short delay to avoid rate limits

    except BotMethodInvalid:
        await message.reply("The bot cannot access the source channel history.")
        forwarding_active = False
    except Exception as e:
        await message.reply(f"An error occurred: {e}")
        forwarding_active = False

@client.on_message(filters.command("stop"))
async def stop_forwarding(client, message):
    global forwarding_active
    forwarding_active = False
    await message.reply("Forwarding has been stopped.")

# HTTP server to handle Koyeb health checks
async def health_check(request):
    return web.Response(text="Bot is running")

def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    web.run_app(app, port=8080)

# Run both the bot and web server concurrently
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(client.start())
    loop.create_task(start_web_server())
    loop.run_forever()
