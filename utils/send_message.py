import requests

def send_message(user_id, text):
    payload = {
        "user_id": user_id,
        "text": text
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(
        'http://stage-splitty-bot:5000/send_message',
        json=payload,
        headers=headers
    )

    return response
