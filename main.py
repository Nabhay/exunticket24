from flask import request, redirect, Response
from monster import render, Flask, escapeString
import sys, json
import hashlib, base64
import secret_parser
import requests, hashlib
from docs import process_docs_in_folder
import resend

app = Flask(__name__)


resend.api_key = secret_parser.parse("variables.txt")["RESEND"]
salt = secret_parser.parse("variables.txt")["SALT"]
db_ip =  secret_parser.parse("variables.txt")["DB_IP"]


daisyui = "<script>"+ open("public/pako.js").read()+ "</script>"+ """<script>
    function decompressGzippedString(base64String) {
        try {
            const binaryString = atob(base64String);
            const len = binaryString.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            const decompressedData = pako.inflate(bytes, { to: 'string' });
            return decompressedData;
        } catch (err) {
            console.error('An error occurred while decompressing the string:', err);
            return null;
        }
    }
    """+ f"""
    var daisycss="{open("public/daisyui.b64").read()}";
    var style=document.createElement("style");
    style.textContent=decompressGzippedString(daisycss);
    document.head.appendChild(style);
    </script>
    """

tailwind = "<script>eval(atob(`" + base64.b64encode(open("public/tailwind.js").read().encode()).decode() + "`))</script>"

@app.get("/")
def home():
    chat_window = open('components/chat_window.html').read()
    previous_chats = open('components/previous_chats.html').read()
    channels = open('components/channels.html').read()
    return render("index", locals() | globals())

@app.get('/get_sum')
def get_sum():
    try:
        user = request.args.get('email')
        if not user:
            return json.dumps({"error": "Email parameter is required."}), 400
        user_access_response = requests.get(f'{db_ip}/get', params={'table': 'user_access', 'key': user})
        if user_access_response.status_code != 200:
            return json.dumps({"error": "Failed to fetch user access."}), 500
        user_access = json.loads(user_access_response.text)

        channels_response = requests.get(f'{db_ip}/get_all', params={'table': 'channels'})
        if channels_response.status_code != 200:
            return json.dumps({"error": "Failed to fetch channels."}), 500
        channels = json.loads(channels_response.text)

        channels_hash = {}
        for channel_id, channel_data in channels.items():
            try:
                channel_info = json.loads(channel_data)
                if channel_id in user_access or channel_info['type'] == 'announcements':
                    channels_hash[channel_info['name']] = hashlib.sha256(channel_data.encode('utf-8')).hexdigest()
            except json.JSONDecodeError:
                print(f"Error decoding JSON for channel data: {channel_data}")
                continue

        return json.dumps(channels_hash), 200
    
    except Exception as e:
        print(f"Error in get_sum: {e}")
        return json.dumps({"error": str(e)}), 500


@app.get('/get_chats')
def get_chats():
    try:
        user = request.args.get('email')
        if not user:
            return json.dumps({"error": "Email parameter is required."}), 400
        
        channel_ids = request.args.getlist('channel_ids')
        
        user_access_response = requests.get(f'{db_ip}/get', params={'table': 'user_access', 'key': user})
        if user_access_response.status_code != 200:
            return json.dumps({"error": "Failed to fetch user access."}), 500
        user_access = json.loads(user_access_response.text)
        
        channels_response = requests.get(f'{db_ip}/get_all', params={'table': 'channels'})
        if channels_response.status_code != 200:
            return json.dumps({"error": "Failed to fetch channels."}), 500
        channels = json.loads(channels_response.text)

        user_channels = {}
        for channel_id, channel_data in channels.items():
            try:
                channel_info = json.loads(channel_data)
                if (channel_id in user_access or channel_info['type'] == 'announcements') and channel_id in channel_ids:
                    user_channels[channel_info['name']] = channel_data
            except json.JSONDecodeError:
                print(f"Error decoding JSON for channel data: {channel_data}")
                continue

        return json.dumps(user_channels), 200
    
    except Exception as e:
        print(f"Error in get_chats: {e}")
        return json.dumps({"error": str(e)}), 500
@app.get('/send_message')
def send_message_user():
    user = request.args.get('email')
    message = request.args.get('channel')
    channel_id = request.args.get('channel')
    requests.get(f'{db_ip}/', params={'channel':channel_id, 'message': message, })
    '''
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

    '''
app.run(host="127.0.0.1", port=int(sys.argv[1]))
