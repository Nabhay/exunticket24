from flask import request, redirect, Response
from monster import render, Flask, escapeString
import sys, json
import hashlib, base64
import secret_parser
import requests, hashlib
import docs
import resend
import aiohttp
import os
import tracemalloc

tracemalloc.start()

app = Flask(__name__)

salt = secret_parser.parse("variables.txt")["SALT"]
db_ip = secret_parser.parse("variables.txt")["DB_IP"]
ai_ip = secret_parser.parse("variables.txt")["AI_IP"]

# Embedding daisyui and tailwind styles
daisyui = "<script>" + open("public/pako.js").read() + "</script>" + """<script>
    function decompressGzippedString(base64String) {
        try {
            const binaryString = atob(base64String);x
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
    """ + f"""
    var daisycss="{open("public/daisyui.b64").read()}";
    var style=document.createElement("style");
    style.textContent=decompressGzippedString(daisycss);
    document.head.appendChild(style);
    </script>
    """

tailwind = "<script>eval(atob(`" + base64.b64encode(open("public/tailwind.js").read().encode()).decode() + "`))</script>"

# Home route
@app.get("/")
def home():
    return render("index", locals() | globals())

# Get sum route
@app.get('/get_sum')
def get_sum():
    try:
        user = request.cookies.get('email')
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
        for channel in channels:
            try:

                channel_info = json.loads(channel[1])
                if str(channel[0]) in str(user_access) or channel_info['type'] == 'announcements':
                    channels_hash[channel[0]] = hashlib.sha256(channel[1].encode('utf-8')).hexdigest()
            except json.JSONDecodeError:
                print(f"Error decoding JSON for channel data: {channel[1]}")
                continue

        return json.dumps(channels_hash), 200

    except Exception as e:
        print(f"Error in get_sum: {e}")
        return json.dumps({"error": str(e)}), 500

# Get chats route
@app.get('/get_chats')
def get_chats():
    try:
        user = request.cookies.get('email')
        if not user:
            return json.dumps({"error": "Email parameter is required."}), 400

        channel_ids = json.loads(request.args.get('channel_ids'))

        user_access_response = requests.get(f'{db_ip}/get', params={'table': 'user_access', 'key': user})
        if user_access_response.status_code != 200:
            return json.dumps({"error": "Failed to fetch user access."}), 500
        user_access = json.loads(user_access_response.text)

        channels_response = requests.get(f'{db_ip}/get_all', params={'table': 'channels'})
        if channels_response.status_code != 200:
            return json.dumps({"error": "Failed to fetch channels."}), 500
        channels = json.loads(channels_response.text)

        user_channels = {}
        for channel in channels:
            try:
                channel_info = json.loads(channel[1])
                if str(channel[0]) in str(channel_ids) and (str(channel[0]) in str(user_access) or channel_info['type'] == 'announcements'):
                    user_channels[channel[0]] = channel_info
            except json.JSONDecodeError:
                print(f"Error decoding JSON for channel data: {channel[1]}")
                continue

        return json.dumps(user_channels), 200

    except Exception as e:
        print(f"Error in get_chats: {e}")
        return json.dumps({"error": str(e)}), 500

# Send message route
@app.get('/api/send_message')
def send_message_user():
    user = request.cookies.get('email')
    message = request.args.get('message')
    channel_id = request.args.get('channel')

    if not user:
        return json.dumps({"error": "User email not found in cookies"}), 400
    if not message:
        return json.dumps({"error": "Message is required"}), 400
    if not channel_id or not channel_id.isdigit():
        return json.dumps({"error": "Valid channel ID is required"}), 400

    try:
        # Step 1: Check if the user has access to the channel
        access_response = requests.get(f'{db_ip}/get', params={'table': 'user_access', 'key': user})
        if access_response.status_code != 200:
            return json.dumps({"error": "Failed to fetch user access"}), 500
        allowed_channels = str(access_response.content)
        if channel_id not in allowed_channels:
            return json.dumps({'error': 'User does not have access to this channel'}), 403

        # Step 2: Send the message via the backer backend
        send_response = requests.get(f'{db_ip}/send_message', params={'channel': channel_id, 'message': message, 'user': user})
        
        if send_response.status_code == 200:
            send_result = send_response.json()

            # Step 3: If the message was successfully sent, check if AI is enabled
            if send_result.get('success'):
                channels_response = requests.get(f'{db_ip}/get', params={'table': 'channels', 'key': channel_id})
                if channels_response.status_code == 200:
                    channel_data = json.loads(channels_response.text)

                    # Step 4: Check if AI is enabled for the channel
                    if channel_data.get('AI_enabled') == True:
                        # Call the Flask AI service
                        ai_response = requests.post(
                            f'http://{ai_ip}/send_message_ai',
                            json={"channel_id": channel_id, "message": message}
                        )

                        if ai_response.status_code == 200:
                            return ai_response.json(), 200
                        else:
                            return json.dumps({"error": "Failed to contact AI service"}), 500

            return send_result, 200

        else:
            return send_response.json(), send_response.status_code

    except requests.exceptions.RequestException as e:
        print(f"Error communicating with the backer backend: {e}")
        return json.dumps({"error": "Failed to communicate with the backer backend"}), 500

@app.get('/api/create_channel')
def create_channel_api():
    user = request.cookies.get('email')
    name = request.args.get('name')
    message = request.args.get('message')

    if not user:
        return json.dumps({"error": "User email not found in cookies"}), 400
    if not name:
        return json.dumps({"error": "Channel name is required"}), 400
    if not message:
        return json.dumps({"error": "Message is required"}), 400

    params = {
        'name': name,
        'user': user
    }

    try:
        create_response = requests.get(f'{db_ip}/create_chat', params=params)

        if create_response.status_code == 200:
            create_data = create_response.json()
            if create_data.get('success'):
                channel_id = create_data.get('channel_id')

                send_params = {
                    'channel': channel_id,
                    'message': message,
                    'user': user
                }
                send_response = requests.get(f'{db_ip}/send_message', params=send_params)

                if send_response.status_code == 200:
                    return json.dumps({"success": True, "message": "Channel created and message sent successfully."}), 200
                else:
                    return json.dumps({"error": "Channel created but failed to send message."}), send_response.status_code
            else:
                return json.dumps({"error": create_data.get('error')}), 400
        else:
            return json.dumps(create_response.json()), create_response.status_code

    except requests.exceptions.RequestException as e:
        print(f"Error communicating with the backer backend: {e}")
        return json.dumps({"error": "Failed to communicate with backer backend"}), 500

@app.get('/api/toggle_ai')
def toggle_ai_api():
    user = request.cookies.get('email')  
    channel = request.args.get('channel')  
    toggle = request.args.get('toggle')     
    
    
    if not user:
        return json.dumps({"error": "User email not found in cookies"}), 400
    if not channel or not channel.isdigit():
        return json.dumps({"error": "Valid channel ID is required"}), 400
    if toggle not in ["true", "false"]:
        return json.dumps({"error": "Toggle value must be 'true' or 'false'"}), 400

    try:
        toggle_params = {
            'channel': channel,
            'toggle': toggle
        }
        toggle_response = requests.get(f'{db_ip}/toggle_ai', params=toggle_params)

        if toggle_response.status_code == 200:
            toggle_data = toggle_response.json()
            if toggle_data.get('success'):
                return json.dumps({"success": True, "message": f"AI has been {'enabled' if toggle == 'true' else 'disabled'} for channel {channel}."}), 200
            else:
                return json.dumps({"error": toggle_data.get('error')}), 400
        else:
            return json.dumps({"error": "Failed to communicate with the backend."}), toggle_response.status_code

    except requests.exceptions.RequestException as e:
        print(f"Error communicating with the backer backend: {e}")
        return json.dumps({"error": "Failed to communicate with the backend."}), 500

app.run(host="127.0.0.1", port=int(sys.argv[1]))
