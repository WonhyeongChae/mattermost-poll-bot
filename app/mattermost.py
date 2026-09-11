import httpx

from app.config import Settings
from app.models import Poll


class MattermostClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.mattermost_base_url.rstrip("/")
        self.bot_token = settings.mattermost_bot_token

    async def create_poll_post(self, poll: Poll, message: str, props: dict) -> str:
        if not self.bot_token:
            raise RuntimeError("MATTERMOST_BOT_TOKEN이 설정되지 않았습니다.")

        payload = {
            "channel_id": poll.channel_id,
            "message": message,
            "props": props,
        }
        headers = {"Authorization": f"Bearer {self.bot_token}"}

        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=15,
        ) as client:
            response = await client.post("/api/v4/posts", json=payload)
            response.raise_for_status()
            body = response.json()

        return str(body["id"])
