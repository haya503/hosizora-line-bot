import pytest
import requests as _requests
from unittest.mock import MagicMock, patch
from line_client import send_messages, send_image_message, reply_message


def _make_ok_resp():
    m = MagicMock()
    m.raise_for_status.return_value = None
    return m


def _make_fail_resp():
    m = MagicMock()
    m.raise_for_status.side_effect = _requests.RequestException("403 Forbidden")
    return m


def test_send_messages_calls_all_targets():
    with patch("line_client.requests.post", return_value=_make_ok_resp()) as mock_post:
        send_messages("tok", ["Uabc", "Cdef"], "hello")
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][1]["json"]["to"] == "Uabc"
    assert mock_post.call_args_list[1][1]["json"]["to"] == "Cdef"


def test_send_messages_uses_correct_auth_header():
    with patch("line_client.requests.post", return_value=_make_ok_resp()) as mock_post:
        send_messages("mytoken", ["Uabc"], "hello")
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer mytoken"


def test_send_messages_continues_on_partial_failure():
    with patch("line_client.requests.post", side_effect=[_make_fail_resp(), _make_ok_resp()]):
        send_messages("tok", ["Ufail", "Uok"], "hello")


def test_send_messages_raises_when_all_fail():
    with patch("line_client.requests.post", return_value=_make_fail_resp()):
        with pytest.raises(RuntimeError, match="all targets"):
            send_messages("tok", ["Ufail"], "hello")


def test_send_image_message_calls_all_targets():
    with patch("line_client.requests.post", return_value=_make_ok_resp()) as mock_post:
        send_image_message("tok", ["Uabc", "Cdef"], "https://example.com/image.jpg")
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][1]["json"]["to"] == "Uabc"
    assert mock_post.call_args_list[1][1]["json"]["to"] == "Cdef"
    # Verify message structure
    msg = mock_post.call_args_list[0][1]["json"]["messages"][0]
    assert msg["type"] == "image"
    assert msg["originalContentUrl"] == "https://example.com/image.jpg"
    assert msg["previewImageUrl"] == "https://example.com/image.jpg"


def test_send_image_message_raises_when_all_fail():
    with patch("line_client.requests.post", return_value=_make_fail_resp()):
        with pytest.raises(RuntimeError, match="all targets"):
            send_image_message("tok", ["Ufail"], "https://example.com/image.jpg")


def test_reply_message_posts_to_reply_endpoint():
    with patch("line_client.requests.post") as mock_post:
        mock_post.return_value = _make_ok_resp()
        reply_message("TOKEN", "REPLY_TOKEN_123", "こんにちは")
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        assert url == "https://api.line.me/v2/bot/message/reply"


def test_reply_message_includes_token_and_text():
    with patch("line_client.requests.post") as mock_post:
        mock_post.return_value = _make_ok_resp()
        reply_message("MY_TOKEN", "RT_456", "テストメッセージ")
        call_kwargs = mock_post.call_args
        headers = call_kwargs[1]["headers"]
        body = call_kwargs[1]["json"]
        assert headers["Authorization"] == "Bearer MY_TOKEN"
        assert body["replyToken"] == "RT_456"
        assert body["messages"][0]["text"] == "テストメッセージ"


def test_reply_message_raises_on_http_error():
    with patch("line_client.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=400)
        mock_post.return_value.raise_for_status.side_effect = Exception("400 Client Error")
        with pytest.raises(Exception):
            reply_message("TOKEN", "RT_789", "テスト")
