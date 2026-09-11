import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Poll, PollOption, Vote


class PollNotFoundError(LookupError):
    pass


class PollClosedError(ValueError):
    pass


class InvalidPollActionError(ValueError):
    pass


class PollPermissionError(PermissionError):
    pass


def get_poll(db: Session, poll_id: str) -> Poll:
    statement = (
        select(Poll)
        .where(Poll.id == poll_id)
        .options(selectinload(Poll.options), selectinload(Poll.votes))
    )
    poll = db.scalar(statement)
    if poll is None:
        raise PollNotFoundError("투표를 찾을 수 없습니다.")
    return poll


def create_poll(
    db: Session,
    *,
    channel_id: str,
    creator_id: str,
    question: str,
    option_labels: list[str],
) -> Poll:
    poll = Poll(
        channel_id=channel_id,
        creator_id=creator_id,
        question=question,
        status="pending",
        action_token=secrets.token_urlsafe(32),
    )
    poll.options = [
        PollOption(label=label, position=index)
        for index, label in enumerate(option_labels, start=1)
    ]
    db.add(poll)
    db.commit()
    return get_poll(db, poll.id)


def activate_poll(db: Session, poll_id: str, post_id: str) -> Poll:
    poll = get_poll(db, poll_id)
    poll.post_id = post_id
    poll.status = "open"
    db.commit()
    db.expire_all()
    return get_poll(db, poll_id)


def remove_poll(db: Session, poll_id: str) -> None:
    poll = get_poll(db, poll_id)
    db.delete(poll)
    db.commit()


def record_vote(
    db: Session,
    *,
    poll_id: str,
    option_id: str,
    user_id: str,
    action_token: str,
) -> Poll:
    poll = get_poll(db, poll_id)
    if not secrets.compare_digest(poll.action_token, action_token):
        raise InvalidPollActionError("유효하지 않은 투표 요청입니다.")
    if poll.status != "open":
        raise PollClosedError("이미 종료된 투표입니다.")
    if option_id not in {option.id for option in poll.options}:
        raise InvalidPollActionError("해당 투표의 선택지가 아닙니다.")

    vote = db.scalar(
        select(Vote).where(Vote.poll_id == poll_id, Vote.user_id == user_id)
    )
    if vote is None:
        db.add(Vote(poll_id=poll_id, option_id=option_id, user_id=user_id))
    else:
        vote.option_id = option_id
        vote.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.expire_all()
    return get_poll(db, poll_id)


def close_poll(
    db: Session,
    *,
    poll_id: str,
    user_id: str,
    action_token: str,
) -> Poll:
    poll = get_poll(db, poll_id)
    if not secrets.compare_digest(poll.action_token, action_token):
        raise InvalidPollActionError("유효하지 않은 종료 요청입니다.")
    if poll.creator_id != user_id:
        raise PollPermissionError("투표 생성자만 종료할 수 있습니다.")
    if poll.status != "open":
        raise PollClosedError("이미 종료된 투표입니다.")

    poll.status = "closed"
    poll.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.expire_all()
    return get_poll(db, poll_id)
