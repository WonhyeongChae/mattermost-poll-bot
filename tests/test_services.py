import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services import (
    InvalidPollActionError,
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


def make_open_poll(db):
    poll = create_poll(
        db,
        channel_id="channel",
        creator_id="creator",
        question="점심 메뉴",
        option_labels=["한식", "중식"],
    )
    return activate_poll(db, poll.id, "post")


def vote(db, poll, option_id, user_id="member"):
    return record_vote(
        db,
        poll_id=poll.id,
        option_id=option_id,
        user_id=user_id,
        post_id="post",
        channel_id="channel",
        action_token=poll.action_token,
    )


def test_user_can_change_vote_without_duplicate_row():
    db = make_session()
    poll = make_open_poll(db)
    first, second = poll.options

    vote(db, poll, first.id)
    changed = vote(db, poll, second.id)

    assert len(changed.votes) == 1
    assert changed.votes[0].option_id == second.id


def test_action_source_must_match_original_post_and_channel():
    db = make_session()
    poll = make_open_poll(db)

    with pytest.raises(InvalidPollActionError):
        record_vote(
            db,
            poll_id=poll.id,
            option_id=poll.options[0].id,
            user_id="member",
            post_id="forged-post",
            channel_id="channel",
            action_token=poll.action_token,
        )


def test_only_creator_can_close_poll():
    db = make_session()
    poll = make_open_poll(db)

    with pytest.raises(PollPermissionError):
        close_poll(
            db,
            poll_id=poll.id,
            user_id="member",
            post_id="post",
            channel_id="channel",
            action_token=poll.action_token,
        )

    closed = close_poll(
        db,
        poll_id=poll.id,
        user_id="creator",
        post_id="post",
        channel_id="channel",
        action_token=poll.action_token,
    )
    assert closed.status == "closed"
