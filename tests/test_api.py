from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app
from app.mattermost import MattermostClient
from app.models import Poll
from app.services import activate_poll, create_poll


@pytest.fixture
def api_context(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    settings = Settings(
        database_url="sqlite:///:memory:",
        public_base_url="https://poll.example.com",
        mattermost_base_url="https://meeting.ssafy.com",
        mattermost_bot_token="bot-token",
        mattermost_command_token="command-token",
    )

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(
        MattermostClient,
        "create_poll_post",
        AsyncMock(return_value="mattermost-post"),
    )

    with TestClient(app) as client:
        yield client, db

    app.dependency_overrides.clear()
    db.close()


def test_slash_command_creates_open_poll(api_context):
    client, db = api_context

    response = client.post(
        "/mattermost/commands/poll",
        data={
            "token": "command-token",
            "user_id": "creator",
            "channel_id": "channel",
            "text": "점심 메뉴 | 한식 | 중식 | 일식",
        },
    )

    assert response.status_code == 200
    assert response.json()["text"] == "투표를 생성했습니다."

    poll = db.scalar(select(Poll))
    assert poll is not None
    assert poll.status == "open"
    assert poll.post_id == "mattermost-post"
    assert len(poll.options) == 3


def test_slash_command_rejects_invalid_token(api_context):
    client, _ = api_context

    response = client.post(
        "/mattermost/commands/poll",
        data={
            "token": "wrong-token",
            "user_id": "creator",
            "channel_id": "channel",
            "text": "질문 | A | B",
        },
    )

    assert response.status_code == 401


def test_vote_callback_updates_message(api_context):
    client, db = api_context
    poll = create_poll(
        db,
        channel_id="channel",
        creator_id="creator",
        question="점심 메뉴",
        option_labels=["한식", "중식"],
    )
    poll = activate_poll(db, poll.id, "post")
    option = poll.options[0]

    response = client.post(
        "/mattermost/actions/vote",
        json={
            "user_id": "member",
            "post_id": "post",
            "channel_id": "channel",
            "context": {
                "poll_id": poll.id,
                "option_id": option.id,
                "action_token": poll.action_token,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["ephemeral_text"] == "투표가 반영되었습니다."
    assert "1표" in response.json()["update"]["props"]["attachments"][0]["text"]


def test_vote_callback_rejects_different_post(api_context):
    client, db = api_context
    poll = create_poll(
        db,
        channel_id="channel",
        creator_id="creator",
        question="점심 메뉴",
        option_labels=["한식", "중식"],
    )
    poll = activate_poll(db, poll.id, "post")

    response = client.post(
        "/mattermost/actions/vote",
        json={
            "user_id": "member",
            "post_id": "forged-post",
            "channel_id": "channel",
            "context": {
                "poll_id": poll.id,
                "option_id": poll.options[0].id,
                "action_token": poll.action_token,
            },
        },
    )

    assert response.status_code == 400
