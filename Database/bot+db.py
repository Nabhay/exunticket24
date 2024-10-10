import discord
from discord.ext import commands
import secret_parser
from flask import Flask, request, jsonify
import litedb
import json
import asyncio
from typing import Dict, Union

secrets = secret_parser.parse('variables.txt')

discord_bot = secrets["discord"]
guild_id = secrets["guild"]

channels = litedb.get_conn("channels")
user_access = litedb.get_conn("user_access")
announcements = litedb.get_conn("announcements")

conn_table = {"channels": channels, "user_access": user_access, "announcements": announcements}

app = Flask('__init__')

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
            conn_table['announcements'].set(name, channel.id)
            struct = {'messages': [], 'type': 'announcements', 'name': name, 'AI_enabled':'false'}
            conn_table['channels'].set(channel.id, json.dumps(struct))
        
        elif category == "chat":
            user_access_data = json.loads(conn_table['user_access'].get(user))
            user_access_data.append(channel.id)
            conn_table['user_access'].set(user, json.dumps(user_access_data))
            struct = {'messages': [], 'type': 'chat', 'name': name, 'AI_enabled':'true'}
            conn_table['channels'].set(channel.id, json.dumps(struct))
        
        return {"success": True, "channel_id": channel.id}
    
    except Exception as e:
        print(f"Error creating channels: {e}")
        return {"error": str(e)}

async def move_channel_by_id(channel_id: int, new_category_name: str):
    try:
        guild = bot.get_guild(guild_id)
        channel = guild.get_channel(channel_id)
        new_category = discord.utils.get(guild.categories, name=new_category_name)
        
        if channel is None:
            return {"error": f'Channel with ID {channel_id} not found.'}
        
        if new_category is None:
            return {"error": f'Category "{new_category_name}" not found.'}

        await channel.edit(category=new_category)
        channels = json.loads(conn_table['channels'].get(channel_id))
        channels['type'] = new_category_name
        conn_table['channels'].set(channel_id, json.dumps(channels))
        return {"success": True, "message": f'Moved channel with ID {channel_id} to category "{new_category_name}".'}
    
    except Exception as e:
        print(f"Error moving channel: {e}")
        return {"error": str(e)}

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return
    
    await bot.process_commands(message)
    
    try:
        if message.channel.name == "announcements" or (message.channel.category and message.channel.category.name in ["tickets", "chat"] and (await message.channel.fetch_message(message.reference.message_id)).author == message.guild.me if message.reference else False):
            channels = json.loads(conn_table['channels'].get(message.channel.id))
            channels["messages"].append({'role': 'Exunite', 'message': message.content, 'time': message.created_at.timestamp(), 'message_id': message.id})
            conn_table['channels'].set(message.channel.id, json.dumps(channels))
    
    except Exception as e:
        print(f"Error handling message: {e}")

@bot.event
async def on_message_edit(before, after):
    if before.author == bot.user:
        return
    
    try:
        if before.channel.category and before.channel.category.name in ["announcements", "tickets", "chat"]:
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
        if message.channel.category and message.channel.category.name in ["announcements", "tickets", "chat"]:
            channels = json.loads(conn_table['channels'].get(message.channel.id))
            channels['messages'] = [msg for msg in channels['messages'] if msg['message_id'] != message.id]
            conn_table['channels'].set(message.channel.id, json.dumps(channels))
    
    except Exception as e:
        print(f"Error handling message delete: {e}")

async def send_message(user_message, identifier, channel_id):
    try:
        channel = bot.get_channel(channel_id)
        message = await channel.send(f'`{identifier}: {user_message}`')
        channels = json.loads(conn_table['channels'].get(message.channel.id))
        channels["messages"].append({'role': identifier, 'message': user_message, 'time': message.created_at.timestamp(), 'message_id': message.id})
        conn_table['channels'].set(message.channel.id, json.dumps(channels))
        return {"success": True}
    
    except Exception as e:
        print(f"Error sending user message: {e}")
        return {"error": str(e)}

@app.get("/get")
def get_api():
    table = request.args.get("table")
    key = request.args.get("key")
    return conn_table[table].get(key)

@app.get("/set")
def set_api():
    table = request.args.get("table")
    key = request.args.get("key")
    value = request.args.get("value")
    conn_table[table].set(key, value)
    return jsonify({"success": True})

@app.get("/delete")
def delete_api():
    table = request.args.get("table")
    key = request.args.get("key")
    conn_table[table].delete(key)
    return jsonify({"success": True})

@app.get("/get_all")
def get_all_api():
    table = request.args.get("table")
    count = request.args.get("count")
    return conn_table[table].get_all()

@app.get("/insert")
def insert_api():
    table = request.args.get("table")
    key = request.args.get("key")
    value = request.args.get("value")
    data = conn_table[table].get(key)
    conn_table[table].set(key, data.append(value))
    return jsonify({"success": True})

@app.get('/move_channel')
def move_channel():
    channel_id = request.args.get('channel_id')
    try:
        result = asyncio.run(move_channel_by_id(int(channel_id), 'tickets'))
        return jsonify(result), 200 if 'success' in result else 400
    except Exception as e:
        print(f"Error moving channel via HTTP: {e}")
        return jsonify({"error": str(e)}), 500

@app.get('/create_chat')
def create_channel():
    name = request.args.get('name')
    user = request.args.get('user')
    try:
        result = asyncio.run(create_channels(name=name, category='chat', user=user))
        return jsonify(result), 200 if 'success' in result else 400
    except Exception as e:
        print(f"Error creating chat via HTTP: {e}")
        return jsonify({"error": str(e)}), 500

@app.get('/send_message')
def send_message_api():
    channel = request.args.get('channel')
    message = request.args.get('message')
    user = request.args.get('user')
    
    try:
        result = asyncio.run(send_message(channel_id=int(channel), user_message=message, identifier=user))
        return jsonify(result), 200 if 'success' in result else 400
    except Exception as e:
        print(f"Error sending user message via HTTP: {e}")
        return jsonify({"error": str(e)}), 500

@app.get('/toggle_ai')
def toggle_ai_api():
    channel = request.args.get('channel', "")
    toggle = request.args.get('toggle', "")
    user = request.args.get('user', "")

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



if __name__ == "__main__":
    bot.loop.create_task(bot.start(secrets["token"]))
    app.run("127.0.0.1", 3000)