from quart import request, redirect, Response
from monster import render, Quart, escapeString
import sys, json
import hashlib, base64
import secret_parser
import requests, hashlib
import docs
import resend
import aiohttp
import os

app = Quart(__name__)

resend.api_key = secret_parser.parse("variables.txt")["RESEND"]
salt = secret_parser.parse("variables.txt")["SALT"]
db_ip = secret_parser.parse("variables.txt")["DB_IP"]

# Embedding daisyui and tailwind styles
daisyui = "<script>" + open("public/pako.js").read() + "</script>" + """<script>
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
    """ + f"""
    var daisycss="{open("public/daisyui.b64").read()}";
    var style=document.createElement("style");
    style.textContent=decompressGzippedString(daisycss);
    document.head.appendChild(style);
    </script>
    """

tailwind = "<script>eval(atob(`" + base64.b64encode(open("public/tailwind.js").read().encode()).decode() + "`))</script>"


async def send_message_ai(channel_id, message):
    try:
        # Load system prompt from file
        system_prompt_file = "system_prompt.txt"
        if os.path.exists(system_prompt_file):
            with open(system_prompt_file, 'r') as f:
                system_prompt = f.read()
        else:
            print("System prompt file not found.")
            return

        # Fetch Google Docs content
        try:
            google_docs_content = docs.process_docs_and_sheets_in_folder('1bO-xjs1sR2Dk7ehXHYxKC0KvH_wTkZy-')
        except Exception as e:
            print(f"Error scraping Google Docs: {e}")
            google_docs_content = "" 

        # Fetch chat history for the specified channel from the backer backend
        chat_history_response = requests.get(f'{db_ip}/get', params={'table': 'channels', 'key': channel_id})
        chat_history = chat_history_response.json()

        # Prepare the request data to send to Gemini API
        request_data = {
            "channel_id": channel_id,
            "message": message,
            "chat_history": chat_history,
            "system_prompt": system_prompt,
            "docs_content": google_docs_content
        }

        # Use multiple API keys in sequence to send the request
        api_keys = secret_parser.parse("variables.txt")["GEMINI_API_KEYS"]
        async with aiohttp.ClientSession() as session:
            for api_key in api_keys:
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                }

                async with session.post('https://gemini-api-endpoint.com/ai_response', json=request_data, headers=headers) as resp:
                    if resp.status == 200:
                        try:
                            response_json = await resp.json()
                            if "response" in response_json and "create_ticket" in response_json:
                                # Send the AI response to the backer backend's /send_message endpoint
                                backer_response = requests.get(
                                    f"{db_ip}/send_message",
                                    params={
                                        "channel": channel_id,
                                        "message": response_json["response"],
                                        "user": "Exun AI"
                                    }
                                )
                                print("AI response sent to the channel.")

                                # Check if a ticket was created, and toggle AI off if so
                                if response_json["create_ticket"]:
                                    toggle_response = requests.get(
                                        f"{db_ip}/toggle_ai",
                                        params={"channel": channel_id, "toggle": "false"}
                                    )
                                    print("AI disabled for the channel.")
                                
                                break  # Exit the loop on success
                            else:
                                print("Unexpected response format:", response_json)
                        except Exception as e:
                            print(f"Error processing response: {e}")
                    else:
                        print(f"Failed to send request using API key: {api_key}. Status code: {resp.status}")

    except Exception as e:
        print(f"Error in send_message_ai: {e}")

# Home route
@app.get("/")
def home():
    chat_window = open('components/chat_window.html').read()
    previous_chats = open('components/previous_chats.html').read()
    channels = open('components/channels.html').read()
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

# Get chats route
@app.get('/get_chats')
def get_chats():
    try:
        user = request.cookies.get('email')
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

# Send message route
@app.get('/api/send_message')
async def send_message_user():
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

        allowed_channels = access_response.json()
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
                        # Call the async function to send the message to the AI
                        await send_message_ai(channel_id, message)

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
