import os
import requests

# --- The only purpose of this script is to test Tasker variables ---

# 1. Define a very clear and unique command and message.
command_part = "THE_COMMAND"
message_part = "THE_MESSAGE"
text_payload = f"{command_part}=:={message_part}"

# 2. Get your API key.
join_api_key = os.environ.get("JOIN_API_KEY")

# 3. Send the push.
if join_api_key:
    print(f"Sending a special test push with payload: {text_payload}")
    base_url = "https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush"
    params = {
        'apikey': join_api_key,
        'deviceId': 'group.phone',
        'text': text_payload
    }
    try:
        requests.get(base_url, params=params, timeout=10)
        print("Push sent successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
else:
    print("Error: JOIN_API_KEY not set.")