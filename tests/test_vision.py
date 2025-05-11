import base64
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts import vision
from scripts.vision import get_async_client


def test_encode_image_to_base64(tmp_path):
    # Create a fake image file
    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"fake image data")

    encoded = vision.encode_image_to_base64(str(fake_img))
    assert isinstance(encoded, str)

    # Decode and verify it matches original
    decoded = base64.b64decode(encoded.encode("utf-8"))
    assert decoded == b"fake image data"


@patch("scripts.vision.AsyncOpenAI")
def test_get_async_client_uses_env_key(mock_openai):
    os.environ["OPENAI_API_KEY"] = "test-key-123"

    client = get_async_client()

    mock_openai.assert_called_once_with(api_key="test-key-123")
    assert client == mock_openai.return_value


@patch("scripts.vision.get_async_client")
@patch("scripts.vision.OpenAI")
@patch(
    "scripts.vision.encode_image_to_base64", return_value="base64-image-data"
)
def test_analyze_image_with_openai(mock_encode, mock_openai, mock_client):
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="example: tag1, tag2"))
    ]
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client

    result = vision.analyze_image_with_openai("fake-image.jpg")

    assert "summary" in result
    assert "tag1" in result["summary"] or "example" in result["summary"]
    mock_encode.assert_called_once()
    mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
@patch("scripts.vision.get_async_client")
async def test_call_openai_chat_success(mock_get_client):
    # Setup mock client and mock .create call
    mock_create = AsyncMock()
    mock_create.return_value.choices = [
        MagicMock(message=MagicMock(content="['usb', 'power']"))
    ]

    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    mock_get_client.return_value = mock_client

    # Call the function
    response = await vision.call_openai_chat(
        "find usb cables", "list tags only"
    )

    # Validate result
    assert "usb" in response
    mock_create.assert_called_once()


@pytest.mark.asyncio
@patch("scripts.vision.get_async_client")
async def test_call_openai_chat_error(mock_get_client, caplog):
    # Mock the client to raise an exception
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=Exception("API fail")
    )
    mock_get_client.return_value = mock_client

    # Trigger the failure
    response = await vision.call_openai_chat("fail this call")

    # Verify results
    assert response == ""
    assert "OpenAI API error" in caplog.text
