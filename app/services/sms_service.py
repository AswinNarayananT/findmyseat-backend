import httpx
from app.core.config import settings

async def send_sms(phone: str, message: str):
    url = f"{settings.INFOBIP_BASE_URL}/sms/2/text/advanced"

    headers = {
        "Authorization": f"App {settings.INFOBIP_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "messages": [
            {
                "from": settings.INFOBIP_SENDER,
                "destinations": [{"to": phone}],
                "text": message,
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)

    return response.json()
