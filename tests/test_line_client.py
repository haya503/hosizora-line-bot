import pytest
import requests as _requests
from unittest.mock import MagicMock, patch
from line_client import send_messages


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
