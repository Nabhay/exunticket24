import litedb
import secret_parser

secrets = secret_parser.parse("variables.txt")

discord_bot = secrets["discord"]
guild_id = secrets["guild"]

channels = litedb.get_conn("channels")
user_access = litedb.get_conn("user_access")

print(channels.get("1299371436011425912"))
