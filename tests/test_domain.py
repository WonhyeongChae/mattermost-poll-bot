import pytest

from app.domain import PollInputError, parse_poll_text


def test_parse_poll_text():
    question, options = parse_poll_text("점심 메뉴 | 한식 | 중식 | 일식")

    assert question == "점심 메뉴"
    assert options == ["한식", "중식", "일식"]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "질문만 있음",
        "질문 | 하나",
        "질문 | 중복 | 중복",
    ],
)
def test_parse_poll_text_rejects_invalid_input(text):
    with pytest.raises(PollInputError):
        parse_poll_text(text)


def test_parse_poll_text_allows_ten_options():
    text = "번호 선택 | " + " | ".join(str(number) for number in range(1, 11))

    _, options = parse_poll_text(text)

    assert len(options) == 10
