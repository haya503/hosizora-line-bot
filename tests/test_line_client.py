from unittest.mock import MagicMock, patch
from line_client import send_message


def test_send_message_posts_to_line_api():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    with patch("line_client.requests.post", return_value=mock_resp) as mock_post:
        send_message("tok123", "uid456", "テストメッセージ")

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["to"] == "uid456"
    assert kwargs["json"]["messages"][0]["text"] == "テストメッセージ"
    assert kwargs["headers"]["Authorization"] == "Bearer tok123"
