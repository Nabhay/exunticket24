import discord
from discord.ext import commands
import time
import secret_parser
from flask import Flask, request, jsonify
import asyncio
import requests
import json


secrets = secret_parser.parse('variables.txt')

discord_bot = secrets["discord"]
guild_id = secrets["guild"]
db_ip = secrets["DB_IP"]
main_ip = secrets["MAIN_IP"]

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
            response = requests.post(f'{db_ip}/set', params={'table': 'announcements', 'key': name, 'value': channel.id})
            response.raise_for_status()
            struct = {'messages': [], 'type': 'announcements', 'name': name}
            response2 = requests.post(f'{db_ip}/set', params={'table': 'channels', 'key': channel.id, 'value': json.dumps(struct)})
            response2.raise_for_status()
        
        elif category == "chat":
            user_access = requests.get(f'{db_ip}/get', params={'table': 'user_access', 'key': user}).json()
            user_access.append(channel.id)
            requests.post(f'{db_ip}/set', params={'table': 'user_access', 'key': user, 'value': json.dumps(user_access)})
            struct = {'messages': [], 'type': 'chat', 'name': name}
            response2 = requests.post(f'{db_ip}/set', params={'table': 'channels', 'key': channel.id, 'value': json.dumps(struct)})
            response2.raise_for_status()
        
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
        channels = requests.get(f'{db_ip}/get', params={'table': 'channels', 'key': channel_id}).json()
        channels['type'] = new_category_name
        confirmation = requests.post(f'{db_ip}/set', params={'table': 'channels', 'key': channel_id, 'value': json.dumps(channels)})
        confirmation.raise_for_status()
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
            channels = requests.get(f'{db_ip}/get', params={'table': 'channels', 'key': message.channel.id}).json()
            channels["messages"].append({'role': 'Exunite', 'message': message.content, 'time': message.created_at.timestamp(), 'message_id': message.id})
            confirmation = requests.post(f'{db_ip}/set', params={'table': 'channels', 'key': message.channel.id, 'value': json.dumps(channels)})
            confirmation.raise_for_status()
    
    except Exception as e:
        print(f"Error handling message: {e}")

@bot.event
async def on_message_edit(before, after):
    if before.author == bot.user:
        return
    
    try:
        if before.channel.category and before.channel.category.name in ["announcements", "tickets", "chat"]:
            channels = requests.get(f'{db_ip}/get', params={'table': 'channels', 'key': before.channel.id}).json()
            for i in range(len(channels['messages'])):
                if channels['messages'][i]['message_id'] == before.id:
                    channels['messages'][i] = {'role': 'Exunite', 'message': after.content, 'time': after.edited_at.timestamp()}
                    confirmation = requests.post(f'{db_ip}/set', params={'table': 'channels', 'key': before.channel.id, 'value': json.dumps(channels)})
                    confirmation.raise_for_status()
    
    except Exception as e:
        print(f"Error handling message edit: {e}")

@bot.event
async def on_message_delete(message: discord.Message):
    if message.author == bot.user:
        return
    
    try:
        if message.channel.category and message.channel.category.name in ["announcements", "tickets", "chat"]:
            channels = requests.get(f'{db_ip}/get', params={'table': 'channels', 'key': message.channel.id}).json()
            channels['messages'] = [msg for msg in channels['messages'] if msg['message_id'] != message.id]
            confirmation = requests.post(f'{db_ip}/set', params={'table': 'channels', 'key': message.channel.id, 'value': json.dumps(channels)})
            confirmation.raise_for_status()
    
    except Exception as e:
        print(f"Error handling message delete: {e}")

async def send_message(user_message, identifier, channel_id):
    try:
        channel = bot.get_channel(channel_id)
        message = await channel.send(f'`{identifier}: {user_message}`')
        channels = requests.get(f'{db_ip}/get', params={'table': 'channels', 'key': message.channel.id}).json()
        channels["messages"].append({'role': identifier, 'message': user_message, 'time': message.created_at.timestamp(), 'message_id': message.id})
        confirmation = requests.post(f'{db_ip}/set', params={'table': 'channels', 'key': message.channel.id, 'value': json.dumps(channels)})
        confirmation.raise_for_status()
        return {"success": True}
    
    except Exception as e:
        print(f"Error sending user message: {e}")
        return {"error": str(e)}


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
def send_message():
    channel = request.args.get('channel')
    message = request.args.get('message')
    user = request.args.get('user')
    try:
        result = asyncio.run(send_message(channel_id=int(channel), user_message=message, identifier=user))
        return jsonify(result), 200 if 'success' in result else 400
    except Exception as e:
        print(f"Error sending user message via HTTP: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    bot.run(discord_bot)
