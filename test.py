import discord
from discord.ext import commands
import secret_parser
from quart import Quart, request, jsonify
import litedb
import json
import asyncio
from typing import Dict, Union
import threading

secrets = secret_parser.parse('variables.txt')

discord_bot = secrets["discord"]
guild_id = secrets["guild"]

channels = litedb.get_conn("channels")
user_access = litedb.get_conn("user_access")

conn_table = {"channels": channels, "user_access": user_access}

conn_table["user_access"].set('me', json.dumps([]))