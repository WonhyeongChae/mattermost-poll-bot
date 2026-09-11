import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Poll, PollOption, Vote, new_id


class PollNotFoundError(LookupError):
    pass


class PollClosedError(ValueError):
    pass


class InvalidPollActionError(ValueError):
    pass


class PollPermissionError(PermissionError):
    pass


def get_poll(db: Session, poll_id: str, *, lock: bool = False) -> Poll:
    statement = (
        select(Poll)
        .where(Poll.id == poll_id)
        .options(selectinload(Poll.options), selectinload(Poll.votes))
    )
    if lock:
        statement = statement.with_for_update()

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
    poll = get_poll(db, poll_id, lock=True)
    poll.post_id = post_id
    poll.status = "open"
    db.commit()
    db.expire_all()
    return get_poll(db, poll_id)


def remove_poll(db: Session, poll_id: str) -> None:
    poll = get_poll(db, poll_id, lock=True)
    db.delete(poll)
    db.commit()


def _validate_action_source(poll: Poll, *, post_id: str, channel_id: str) -> None:
    if poll.post_id != post_id or poll.channel_id != channel_id:
        raise InvalidPollActionError("게시물 또는 채널 정보가 일치하지 않습니다.")


def _upsert_vote(
    db: Session,
    *,
    poll_id: str,
    option_id: str,
    user_id: str,
    updated_at: datetime,
) -> None:
    values = {
        "id": new_id(),
        "poll_id": poll_id,
        "option_id": option_id,
        "user_id": user_id,
        "updated_at": updated_at,
    }
    dialect = db.get_bind().dialect.name

    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert

        statement = insert(Vote).values(**values).on_conflict_do_update(
            constraint="uq_vote_poll_user",
            set_={"option_id": option_id, "updated_at": updated_at},
        )
        db.execute(statement)
        return

    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert

        statement = insert(Vote).values(**values).on_conflict_do_update(
            index_elements=["poll_id", "user_id"],
            set_={"option_id": option_id, "updated_at": updated_at},
        )
        db.execute(statement)
        return

    vote = db.scalar(
        select(Vote)
        .where(Vote.poll_id == poll_id, Vote.user_id == user_id)
        .with_for_update()
    )
    if vote is None:
        db.add(Vote(**values))
    else:
        vote.option_id = option_id
        vote.updated_at = updated_at


def record_vote(
    db: Session,
    *,
    poll_id: str,
    option_id: str,
    user_id: str,
    post_id: str,
    channel_id: str,
    action_token: str,
) -> Poll:
    poll = get_poll(db, poll_id, lock=True)
    if not secrets.compare_digest(poll.action_token, action_token):
        raise InvalidPollActionError("유효하지 않은 투표 요청입니다.")
    _validate_action_source(poll, post_id=post_id, channel_id=channel_id)
    if poll.status != "open":
        raise PollClosedError("이미 종료된 투표입니다.")
    if option_id not in {option.id for option in poll.options}:
        raise InvalidPollActionError("해당 투표의 선택지가 아닙니다.")

    _upsert_vote(
        db,
        poll_id=poll_id,
        option_id=option_id,
        user_id=user_id,
        updated_at=datetime.now(timezone.utc),
    )
    db.commit()
    db.expire_all()
    return get_poll(db, poll_id)


def close_poll(
    db: Session,
    *,
    poll_id: str,
    user_id: str,
    post_id: str,
    channel_id: str,
    action_token: str,
) -> Poll:
    poll = get_poll(db, poll_id, lock=True)
    if not secrets.compare_digest(poll.action_token, action_token):
        raise InvalidPollActionError("유효하지 않은 종료 요청입니다.")
    _validate_action_source(poll, post_id=post_id, channel_id=channel_id)
    if poll.creator_id != user_id:
        raise PollPermissionError("투표 생성자만 종료할 수 있습니다.")
    if poll.status != "open":
        raise PollClosedError("이미 종료된 투표입니다.")

    poll.status = "closed"
    poll.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.expire_all()
    return get_poll(db, poll_id)
