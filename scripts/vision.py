"""Dandles uploading images and sending them to OpenAI's GPT-4 Vision API.

It encodes images in base64, sends them to the model, and extracts object tags
to support image-based inventory search in the application.
"""

import base64
import logging
import os
from pathlib import Path

from openai import AsyncOpenAI, OpenAI

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def encode_image_to_base64(image_path: str) -> str:
    """Generate base64 encoding of image file.

    Args:
        image_path (str): Path to the image file.

    Returns:
        str: Base64-encoded representation of the image.
    """
    with Path.open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_image_with_openai(image_path: str) -> dict:
    """GEt summary of detected objects from AI API.

    Args:
        image_path (str): Path to the local image file.

    Returns:
        dict: Dictionary containing a "summary" field with raw model output
        (typically JSON-formatted).
    """
    image_data = encode_image_to_base64(image_path)
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": ("List the objects in this image for inventory "
                                 "as JSON."),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        },
                    },
                ],
            }
        ],
        max_tokens=500,
    )

    content = response.choices[0].message.content
    return {"summary": content}


def get_async_client() -> AsyncOpenAI:
    """Creates and returns an async OpenAI client with environment API key.

    Returns:
        AsyncOpenAI: Initialized async OpenAI client instance.
    """
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def call_openai_chat(user_prompt: str, system_prompt: str = "") -> str:
    """Sends a chat message to the OpenAI API using the async client.

    Args:
        user_prompt (str): The message from the user.
        system_prompt (str, optional): The system instruction. Defaults to "".

    Returns:
        str: The assistant's response text, or an empty string on error.
    """
    client = get_async_client()
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        logger.exception("OpenAI API error")
        return ""
