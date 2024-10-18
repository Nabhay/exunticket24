import discord
from discord.ext import commands
import secret_parser
from quart import Quart, request, jsonify
import litedb
import json
import asyncio
from typing import Dict, Union
import threading
import traceback

secrets = secret_parser.parse('variables.txt')

discord_bot = secrets["discord"]
guild_id = secrets["guild"]

channels = litedb.get_conn("channels")
user_access = litedb.get_conn("user_access")

conn_table = {"channels": channels, "user_access": user_access}

app = Quart(__name__)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    print("Bot Started")

async def create_channels(name: str, category: str, user):
    try:
        guild = bot.get_guild(guild_id)
        category_channel = discord.utils.get(guild.categories, name=category)

        if category_channel is None:
            return {"error": f"Category '{category}' not found."}

        channel = await guild.create_text_channel(name, category=category_channel)

        if category == "announcements":
            struct = {'messages': [], 'type': 'announcements', 'name': name, 'AI_enabled': 'false'}
            conn_table['channels'].set(channel.id, json.dumps(struct))

        elif category == "restricted-announcements":
            struct = {'messages': [], 'type': 'restricted-announcements', 'name': name, 'AI_enabled': 'false'}
            conn_table['channels'].set(channel.id, json.dumps(struct))

        elif category == "chat":
            user_access_data = json.loads(conn_table['user_access'].get(user))
            user_access_data.append(channel.id)
            conn_table['user_access'].set(user, json.dumps(user_access_data))
            struct = {'messages': [], 'type': 'chat', 'name': name, 'AI_enabled': 'true'}
            conn_table['channels'].set(channel.id, json.dumps(struct))

        return {"success": True, "channel_id": channel.id}

    except Exception as e:
        print(f"Error creating channels: {e}")
        return {"error": str(e)}

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    try:
        if message.channel.category.name in ["announcements", "restricted-announcements"] or \
                (message.channel.category and message.channel.category.name == "chat" and
                 (await message.channel.fetch_message(message.reference.message_id)).author == message.guild.me if message.reference else False):
            channels = json.loads(json.loads(conn_table['channels'].get(str(message.channel.id))))
            channels["messages"].append({'role': 'Exunite', 'message': message.content, 'time': message.created_at.timestamp(), 'message_id': message.id})
            conn_table['channels'].set(message.channel.id, json.dumps(channels))

    except Exception as e:
        print(f"Error handling message: {e}")
        traceback.print_exc()

@bot.event
async def on_message_edit(before, after):
    if before.author == bot.user:
        return

    try:
        if before.channel.category and before.channel.category.name in ["restricted-announcements","announcements", "chat"]:
            channels = json.loads(conn_table['channels'].get(before.channel.id))
            for i in range(len(channels['messages'])):
                if channels['messages'][i]['message_id'] == before.id:
                    channels['messages'][i] = {'role': 'Exunite', 'message': after.content, 'time': after.edited_at.timestamp()}
                    conn_table['channels'].set(before.channel.id, json.dumps(channels))

    except Exception as e:
        print(f"Error handling message edit: {e}")

@bot.event
async def on_message_delete(message: discord.Message):
    if message.author == bot.user:
        return

    try:
        if message.channel.category and message.channel.category.name in ["announcements", "chat", "restricted-announcements"]:
            channels = json.loads(conn_table['channels'].get(message.channel.id))
            channels['messages'] = [msg for msg in channels['messages'] if msg['message_id'] != message.id]
            conn_table['channels'].set(message.channel.id, json.dumps(channels))

    except Exception as e:
        print(f"Error handling message delete: {e}")

async def send_message(user_message, identifier, channel_id):
    try:
        channel = bot.get_channel(channel_id)
        message = await channel.send(f'`{identifier}: {user_message}`')
        channels = json.loads(json.loads(conn_table['channels'].get(message.channel.id)))
        channels["messages"].append({'role': identifier, 'message': user_message, 'time': message.created_at.timestamp(), 'message_id': message.id})
        conn_table['channels'].set(message.channel.id, json.dumps(channels))
        return {"success": True}

    except Exception as e:
        print(f"Error sending user message: {e}")
        return {"error": str(e)}

@app.route("/get", methods=["GET"])
async def get_api():
    table = request.args.get("table")
    key = request.args.get("key")
    return conn_table[table].get(key)

@app.route("/set", methods=["GET"])
async def set_api():
    table = request.args.get("table")
    key = request.args.get("key")
    value = request.args.get("value")
    conn_table[table].set(key, value)
    return jsonify({"success": True})

@app.route("/delete", methods=["GET"])
async def delete_api():
    table = request.args.get("table")
    key = request.args.get("key")
    conn_table[table].delete(key)
    return jsonify({"success": True})

@app.route("/get_all", methods=["GET"])
async def get_all_api():
    table = request.args.get("table")
    return conn_table[table].get_all()

@app.route('/create_chat', methods=["GET"])
async def create_channel():
    name = request.args.get('name')
    user = request.args.get('user')
    try:
        result = await create_channels(name=name, category='chat', user=user)
        return jsonify(result), 200 if 'success' in result else 400
    except Exception as e:
        print(f"Error creating chat via HTTP: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/send_message', methods=["GET"])
async def send_message_api():
    channel = request.args.get('channel')
    message = request.args.get('message')
    user = request.args.get('user')

    try:
        result = await send_message(channel_id=int(channel), user_message=message, identifier=user)
        return jsonify(result), 200 if 'success' in result else 400
    except Exception as e:
        print(f"Error sending user message via HTTP: {e}")
        return jsonify({"error": str(e)}), 500

@app.get('/toggle_ai')
def toggle_ai_api():
    channel = request.args.get('channel', "")
    toggle = request.args.get('toggle', "")

    if not channel.isdigit() or toggle not in ["true", "false"] :
        return jsonify({"error": "Invalid parameters"}), 400

    enable = toggle == "true"

    try:
        result = toggle_ai(int(channel), enable)
        return jsonify(result), 200
    except Exception as e:
        print(f"Error toggling AI: {e}")
        return jsonify({"error": str(e)}), 500

def toggle_ai(channel: int, enable: bool) -> Dict[str, Union[bool, str]]:
    try:
        channels_data = json.loads(conn_table['channels'].get(channel))
        channels_data['AI_enabled'] = enable
        conn_table['channels'].set(channel, json.dumps(channels_data))
        return {"success": True}
    except Exception as e:
        print(f"Error toggling AI: {e}")
        return {"error": str(e)}

async def create_restricted_channel(channel: str, allowed: list) -> Dict[str, any]:
    try:
        for user_id in allowed:
            response = await create_channels(name=channel, category="restricted-announcements")
            
            if response.get("success"):
                channel_id = response["channel_id"]
                user_access_data = user_access.get(user_id)
                if user_access_data:
                    user_access_list = json.loads(user_access_data)
                else:
                    user_access_list = []
                user_access_list.append(channel_id)
                conn_table['user_access'].set(user_id, json.dumps(user_access_list))
            else:
                return {"error": f"Failed to create channel for user {user_id}: {response.get('error')}"}
        
        return {"success": True, "message": f"Restricted channel '{channel}' created and access granted to specified users."}
    
    except Exception as e:
        print(f"Error creating restricted channel: {e}")
        return {"error": str(e)}

@bot.command(name='create_restricted')
async def create_restricted(ctx, channel: str, *allowed_users: str):
    result = await create_restricted_channel(channel, list(allowed_users))
    if result.get("success"):
        await ctx.send(result["message"])
    else:
        await ctx.send(f"Error: {result.get('error')}")

async def run_discord_bot():
    await bot.start(discord_bot)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(run_discord_bot())
    app.run(host="127.0.0.1", port=3000, loop=loop)
