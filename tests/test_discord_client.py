from unittest.mock import patch, MagicMock
import requests
import pytest
import discord_client

WEBHOOK_URL = "https://discord.com/api/webhooks/123/abc"


def test_send_message_posts_to_webhook():
    with patch("discord_client.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=204)
        discord_client.send_message(WEBHOOK_URL, "テストメッセージ")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == WEBHOOK_URL
        assert kwargs["json"]["content"] == "テストメッセージ"


def test_send_message_truncates_long_text():
    long_text = "あ" * 3000
    with patch("discord_client.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=204)
        discord_client.send_message(WEBHOOK_URL, long_text)
        sent = mock_post.call_args[1]["json"]["content"]
        assert len(sent) <= 2000


def test_send_message_raises_on_http_error():
    with patch("discord_client.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("400 Bad Request")
        mock_post.return_value = mock_resp
        with pytest.raises(requests.HTTPError):
            discord_client.send_message(WEBHOOK_URL, "エラーテスト")


def test_send_embed_with_image_sends_embed():
    with patch("discord_client.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=204)
        discord_client.send_embed_with_image(WEBHOOK_URL, "テキスト", "https://example.com/img.jpg")
        args, kwargs = mock_post.call_args
        assert args[0] == WEBHOOK_URL
        body = kwargs["json"]
        assert body["content"] == "テキスト"
        assert body["embeds"][0]["image"]["url"] == "https://example.com/img.jpg"


def test_send_embed_with_image_truncates_long_text():
    long_text = "あ" * 3000
    with patch("discord_client.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=204)
        discord_client.send_embed_with_image(WEBHOOK_URL, long_text, "https://example.com/img.jpg")
        sent = mock_post.call_args[1]["json"]["content"]
        assert len(sent) <= 2000
