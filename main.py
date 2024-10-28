from flask import request, redirect, Response, make_response
from monster import render, Flask, escapeString
import sys, json
import hashlib, base64
import secret_parser
import requests, hashlib
import tracemalloc

tracemalloc.start()

app = Flask(__name__)

salt = secret_parser.parse("variables.txt")["SALT"]
db_ip = secret_parser.parse("variables.txt")["DB_IP"]
ai_ip = secret_parser.parse("variables.txt")["AI_IP"]
main_ip = secret_parser.parse("variables.txt")["MAIN_IP"]
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
    user = request.cookies.get('email')
    if type(user) == None or not authd():
        return redirect('https://reg.exunclan.com/login?redirect=queries')
    return render("index", locals() | globals())

# Get sum route
@app.get('/get_sum')
def get_sum():
    try:
        user = request.cookies.get('email')
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
def send_message_to_channel(user, message, channel_id):
    try:
        # Step 1: Check if the user has access to the channel
        access_response = requests.get(f'{db_ip}/get', params={'table': 'user_access', 'key': user})
        if access_response.status_code != 200:
            return json.dumps({"error": "Failed to fetch user access"}), 500
        allowed_channels = str(access_response.text)
        if channel_id not in allowed_channels:
            return json.dumps({'error': 'User does not have access to this channel'}), 403
        channels_response = requests.get(f'{db_ip}/get', params={'table': 'channels', 'key': channel_id})
        if channels_response.status_code != 200:
            return json.dumps({"error": "Channel does not exist"})
        channel_data = json.loads(channels_response.text)
        if channel_data.get("type", "").lower() == 'restricted-announcements':
            return json.dumps({"error": 'Channel is restricted'})
        # Step 2: Send the message via the backer backend
        send_response = requests.get(f'{db_ip}/send_message', params={'channel': channel_id, 'message': message, 'user': user})
        
        if send_response.status_code == 429:
            return json.dumps({"error": "Rate limit exceeded"}), 429

        if send_response.status_code == 200:
            send_result = send_response.json()
            # Step 3: If the message was successfully sent, check if AI is enabled
            if send_result.get('success'):
                # Step 4: Check if AI is enabled for the channel
                if str(channel_data.get('AI_enabled')).lower() == "true":
                    ai_response = requests.get(
                        f'{ai_ip}/send_message_ai',
                        params={"channel_id": channel_id, "message": message}
                    )

                    if ai_response.status_code == 200:
                        return ai_response, 200
                    else:
                        return json.dumps({"error": "Failed to contact AI service"}), 500

            return send_result, 200

        else:
            return send_response.json(), send_response.status_code

    except requests.exceptions.RequestException as e:
        print(f"Error communicating with the backend: {e}")
        return {"error": "Failed to communicate with the backend"}, 500

# API endpoint that calls the helper function
@app.get('/api/send_message')
def send_message_user():
    user = request.cookies.get('email')
    message = request.args.get('message')
    channel_id = request.args.get('channel')

    if not message:
        return {"error": "Message is required"}, 400
    if not channel_id or not channel_id.isdigit():
        return {"error": "Valid channel ID is required"}, 400

    return send_message_to_channel(user, message, channel_id)

@app.get('/api/create_channel')
def create_channel_api():
    user = request.cookies.get('email')
    name = request.args.get('name')
    message = request.args.get('message')
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
                send_response = send_message_to_channel(user, message, str(channel_id))

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
    if not channel or not channel.isdigit():
        return json.dumps({"error": "Valid channel ID is required"}), 400
    if toggle not in ["true", "false"]:
        return json.dumps({"error": "Toggle value must be 'true' or 'false'"}), 400
    access_response = requests.get(f'{db_ip}/get', params={'table': 'user_access', 'key': user})
    if access_response.status_code != 200:
        return json.dumps({"error": "Failed to fetch user access"}), 500
    allowed_channels = str(access_response.content)
    if channel not in allowed_channels:
        return json.dumps({'error': 'User does not have access to this channel'}), 403 
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


@app.get('/auth')
def auth():
    auth_token = request.args.get('auth_token')
    email = request.args.get('email')
    if requests.get(f'{db_ip}/get', params={'table':'user_access', 'key': email}).status_code == 204:
        requests.get(f'{db_ip}/set', params={'table':'user_access', 'key': email, 'value':'[]'})
    resp = make_response(redirect('/'))  
    resp.set_cookie('email', email)
    resp.set_cookie('auth_token', auth_token)
    return resp 

def authd():
    try:
        if "auth_token" not in request.cookies or "email" not in request.cookies:
            return False
        if request.cookies["auth_token"]==auth_token(request.cookies["email"]):
            return True
        return False
    except:
        return False
    
def auth_token(a):
    if type(a) == str:
        a = a.encode()+salt.encode()
    return hashlib.sha256(a).hexdigest()


app.run(host="127.0.0.1", port=int(sys.argv[1]))