import secrets
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Form, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import Base, engine, get_db
from app.domain import PollInputError, build_poll_props, parse_poll_text
from app.mattermost import MattermostClient
from app.services import (
    InvalidPollActionError,
    PollClosedError,
    PollNotFoundError,
    PollPermissionError,
    activate_poll,
    close_poll,
    create_poll,
    record_vote,
    remove_poll,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Mattermost Poll Bot", version="0.1.0", lifespan=lifespan)


class ActionContext(BaseModel):
    poll_id: str
    action_token: str
    option_id: str | None = None


class ActionRequest(BaseModel):
    user_id: str
    post_id: str | None = None
    channel_id: str | None = None
    context: ActionContext


def _verify_command_token(received: str, settings: Settings) -> None:
    if not settings.mattermost_command_token:
        raise HTTPException(status_code=503, detail="Mattermost command token is not configured.")
    if not secrets.compare_digest(received, settings.mattermost_command_token):
        raise HTTPException(status_code=401, detail="Invalid Mattermost command token.")


def _action_error(error: Exception) -> HTTPException:
    if isinstance(error, PollNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, PollPermissionError):
        return HTTPException(status_code=403, detail=str(error))
    if isinstance(error, (PollClosedError, InvalidPollActionError)):
        return HTTPException(status_code=400, detail=str(error))
    return HTTPException(status_code=500, detail="Unexpected poll error.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/mattermost/commands/poll")
async def create_poll_command(
    token: str = Form(...),
    user_id: str = Form(...),
    channel_id: str = Form(...),
    text: str = Form(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    _verify_command_token(token, settings)

    try:
        question, options = parse_poll_text(text)
    except PollInputError as error:
        return {
            "response_type": "ephemeral",
            "text": (
                f"투표를 만들 수 없습니다: {error}\n"
                "사용법: /poll 질문 | 선택지 1 | 선택지 2"
            ),
        }

    poll = create_poll(
        db,
        channel_id=channel_id,
        creator_id=user_id,
        question=question,
        option_labels=options,
    )

    try:
        poll.status = "open"
        props = build_poll_props(poll, settings.public_base_url)
        post_id = await MattermostClient(settings).create_poll_post(poll, "", props)
        activate_poll(db, poll.id, post_id)
    except (httpx.HTTPError, RuntimeError, KeyError) as error:
        remove_poll(db, poll.id)
        raise HTTPException(
            status_code=502,
            detail="Mattermost에 투표 게시물을 생성하지 못했습니다.",
        ) from error

    return {
        "response_type": "ephemeral",
        "text": "투표를 생성했습니다.",
    }


@app.post("/mattermost/actions/vote")
def vote_action(
    request: ActionRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    if request.context.option_id is None:
        raise HTTPException(status_code=400, detail="선택지 정보가 없습니다.")

    try:
        poll = record_vote(
            db,
            poll_id=request.context.poll_id,
            option_id=request.context.option_id,
            user_id=request.user_id,
            action_token=request.context.action_token,
        )
    except Exception as error:
        if isinstance(
            error,
            (PollNotFoundError, PollPermissionError, PollClosedError, InvalidPollActionError),
        ):
            raise _action_error(error) from error
        raise

    return {
        "update": {
            "message": "",
            "props": build_poll_props(poll, settings.public_base_url),
        },
        "ephemeral_text": "투표가 반영되었습니다.",
    }


@app.post("/mattermost/actions/close")
def close_action(
    request: ActionRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        poll = close_poll(
            db,
            poll_id=request.context.poll_id,
            user_id=request.user_id,
            action_token=request.context.action_token,
        )
    except Exception as error:
        if isinstance(
            error,
            (PollNotFoundError, PollPermissionError, PollClosedError, InvalidPollActionError),
        ):
            raise _action_error(error) from error
        raise

    return {
        "update": {
            "message": "",
            "props": build_poll_props(poll, settings.public_base_url),
        },
        "ephemeral_text": "투표를 종료했습니다.",
    }
