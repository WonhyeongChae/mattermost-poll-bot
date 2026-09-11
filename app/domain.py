from app.models import Poll

MIN_OPTIONS = 2
MAX_OPTIONS = 10


class PollInputError(ValueError):
    pass


def parse_poll_text(text: str) -> tuple[str, list[str]]:
    parts = [part.strip() for part in text.split("|")]
    if not parts or not parts[0]:
        raise PollInputError("질문을 입력해야 합니다.")

    question = parts[0]
    options = [option for option in parts[1:] if option]

    if len(question) > 300:
        raise PollInputError("질문은 300자 이하여야 합니다.")
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        raise PollInputError(f"선택지는 {MIN_OPTIONS}개 이상 {MAX_OPTIONS}개 이하여야 합니다.")
    if any(len(option) > 120 for option in options):
        raise PollInputError("각 선택지는 120자 이하여야 합니다.")
    if len({option.casefold() for option in options}) != len(options):
        raise PollInputError("중복된 선택지는 사용할 수 없습니다.")

    return question, options


def render_poll_message(poll: Poll) -> str:
    vote_counts = {option.id: 0 for option in poll.options}
    for vote in poll.votes:
        vote_counts[vote.option_id] = vote_counts.get(vote.option_id, 0) + 1

    status = "진행 중" if poll.status == "open" else "종료"
    lines = [f"## 🗳️ {poll.question}", "", f"상태: **{status}**", ""]

    for option in poll.options:
        lines.append(f"{option.position}. **{option.label}** — {vote_counts[option.id]}표")

    lines.extend(["", f"총 {len(poll.votes)}명 참여"])
    return "\n".join(lines)


def build_poll_props(poll: Poll, public_base_url: str) -> dict:
    message = render_poll_message(poll)
    if poll.status != "open":
        return {"attachments": [{"text": message}]}

    vote_actions = []
    for option in poll.options:
        vote_actions.append(
            {
                "id": f"vote-{option.id}",
                "name": f"{option.position}. {option.label}",
                "type": "button",
                "integration": {
                    "url": f"{public_base_url.rstrip('/')}/mattermost/actions/vote",
                    "context": {
                        "poll_id": poll.id,
                        "option_id": option.id,
                        "action_token": poll.action_token,
                    },
                },
            }
        )

    attachments = []
    for index in range(0, len(vote_actions), 5):
        attachments.append(
            {
                "text": message if index == 0 else "",
                "actions": vote_actions[index : index + 5],
            }
        )

    attachments.append(
        {
            "actions": [
                {
                    "id": f"close-{poll.id}",
                    "name": "투표 종료",
                    "type": "button",
                    "style": "danger",
                    "integration": {
                        "url": f"{public_base_url.rstrip('/')}/mattermost/actions/close",
                        "context": {
                            "poll_id": poll.id,
                            "action_token": poll.action_token,
                        },
                    },
                }
            ]
        }
    )
    return {"attachments": attachments}
