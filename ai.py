from quart import Quart, request, jsonify
import os
import google.generativeai as genai
import secret_parser
import docs
import aiohttp
import json
import requests

app = Quart(__name__)

db_ip = secret_parser.parse("variables.txt")["DB_IP"]
api_keys = eval(
    secret_parser.parse("variables.txt")["GEMINI_API_KEYS"]
)  # Assuming this is a list
request_count = 0
current_key_index = 0

# Configure the initial API key
genai.configure(api_key=api_keys[current_key_index])


@app.get("/send_message_ai")
async def send_message_ai():
    global request_count, current_key_index  # Use global to track requests and current API key index
    channel_id = request.args.get("channel_id")
    message = request.args.get("message")

    try:
        # Load the system prompt
        system_prompt_file = "system_prompt.txt"
        if os.path.exists(system_prompt_file):
            with open(system_prompt_file, "r") as f:
                system_prompt = f.read()
        else:
            return jsonify({"error": "System prompt file not found."}), 404

        # Fetch Google Docs content
        try:
            google_docs_content = docs.process_docs_and_sheets_in_folder(
                "1bO-xjs1sR2Dk7ehXHYxKC0KvH_wTkZy-"
            )
        except Exception as e:
            print(f"Error scraping Google Docs: {e}")
            google_docs_content = ""

        # Fetch chat history for the specified channel from the backend
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{db_ip}/get", params={"table": "channels", "key": channel_id}
            ) as resp:
                data = await resp.read()
                chat_history = json.loads(data)

        # Combine system prompt and Google Docs content for system instruction
        system_instruction = (
            f"{system_prompt}\n\nTreat the following information as very important\n\n{google_docs_content}\n\n"
            "Please respond strictly in JSON format with this schema:\n"
            "{\n"
            '  "response": "(string containing the answer)",\n'
            '  "create_ticket": "(string with ticket information or status)"\n'
            "}"
        )

        # Initialize the GenerativeModel with the dynamic system instruction
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash", system_instruction=system_instruction
        )

        # Define the prompt for the Gemini API
        prompt = f"{message}\n\nChat History: {chat_history}"

        # Select the current API key
        api_key = api_keys[current_key_index]

        # Reconfigure the API key if switching keys
        genai.configure(api_key=api_key)

        # Generate content using the GenerativeModel with the defined prompt
        response = model.generate_content(prompt)
        reply = response.text.strip("`json")
        # Log the raw response
        print("Raw response:", reply)

        # Attempt to parse the JSON response
        try:
            response_data = json.loads(reply)
        except json.JSONDecodeError:
            return jsonify({"error": "Received non-JSON response from the API."}), 500
        
        send_message = requests.get(f'{db_ip}/send_message?channel={channel_id}&user=Exun AI&message={response_data['response']}')
        if response_data['create_ticket'] == "true":
            toggle_ai = requests.get(f'{db_ip}/toggle_ai?channel={channel_id}&toggle=false')

        # Increment the request count
        request_count += 1

        # Switch to the next API key every 15 requests
        if request_count % 15 == 0:
            current_key_index = (current_key_index + 1) % len(
                api_keys
            )  # Rotate to the next key
            genai.configure(
                api_key=api_keys[current_key_index]
            )  # Reconfigure with the new API key

        # Return the response in JSON format
        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)
