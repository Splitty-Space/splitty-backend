import aiohttp

async def send_message(user_id, text):
    url = 'http://stage-splitty-bot:5000/send_message'
    payload = {
        "user_id": user_id,
        "text": text
    }
    headers = {
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            return await response.text()
