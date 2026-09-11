from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services import (
    PollPermissionError,
    activate_poll,
    close_poll,
    create_poll,
    record_vote,
)


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_user_can_change_vote():
    db = make_session()
    poll = create_poll(
        db,
        channel_id="channel",
        creator_id="creator",
        question="점심 메뉴",
        option_labels=["한식", "중식"],
    )
    poll = activate_poll(db, poll.id, "post")
    first, second = poll.options

    record_vote(
        db,
        poll_id=poll.id,
        option_id=first.id,
        user_id="member",
        action_token=poll.action_token,
    )
    changed = record_vote(
        db,
        poll_id=poll.id,
        option_id=second.id,
        user_id="member",
        action_token=poll.action_token,
    )

    assert len(changed.votes) == 1
    assert changed.votes[0].option_id == second.id


def test_only_creator_can_close_poll():
    db = make_session()
    poll = create_poll(
        db,
        channel_id="channel",
        creator_id="creator",
        question="점심 메뉴",
        option_labels=["한식", "중식"],
    )
    poll = activate_poll(db, poll.id, "post")

    try:
        close_poll(
            db,
            poll_id=poll.id,
            user_id="member",
            action_token=poll.action_token,
        )
    except PollPermissionError:
        pass
    else:
        raise AssertionError("PollPermissionError was not raised")

    closed = close_poll(
        db,
        poll_id=poll.id,
        user_id="creator",
        action_token=poll.action_token,
    )
    assert closed.status == "closed"
