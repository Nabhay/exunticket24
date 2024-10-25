# ai_service.py

from quart import Quart, request, jsonify
import os
import aiohttp
import json
import secret_parser
import docs
import requests

app = Quart(__name__)

db_ip = secret_parser.parse("variables.txt")["DB_IP"]

@app.route('/send_message_ai', methods=['POST'])
async def send_message_ai():
    data = request.json
    channel_id = data.get('channel_id')
    message = data.get('message')

    try:
        # Load system prompt from file
        system_prompt_file = "system_prompt.txt"
        if os.path.exists(system_prompt_file):
            with open(system_prompt_file, 'r') as f:
                system_prompt = f.read()
        else:
            return jsonify({"error": "System prompt file not found."}), 404

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
                            return jsonify(response_json), 200
                        except Exception as e:
                            return jsonify({"error": f"Error processing AI response: {e}"}), 500
                    else:
                        print(f"Failed to send request using API key: {api_key}. Status code: {resp.status}")

        return jsonify({"error": "Failed to process AI message."}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host="127.0.0.1", port=5001)
