"""This module handles uploading images and sending them to OpenAI's GPT-4
Vision API.

It encodes images in base64, sends them to the model, and extracts
object tags to support image-based inventory search in the application.
"""

import base64
import logging
import os

from openai import AsyncOpenAI, OpenAI


def encode_image_to_base64(image_path: str) -> str:
    """Reads an image file and encodes it to a base64 string for inclusion in
    API requests.

    Args:
        image_path (str): Path to the image file.

    Returns:
        str: Base64-encoded representation of the image.
    """
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_image_with_openai(image_path: str) -> dict:
    """Sends an image to OpenAI's GPT-4 Vision model and retrieves a summary of
    detected objects.

    Args:
        image_path (str): Path to the local image file.

    Returns:
        dict: Dictionary containing a "summary" field with raw model output (typically JSON-formatted).
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
                        "text": "List the objects in this image for inventory as JSON.",
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
    print(content)
    return {"summary": content}


def get_async_client() -> AsyncOpenAI:
    """Creates and returns an asynchronous OpenAI client using the API key from
    environment.

    Returns:
        AsyncOpenAI: Initialized async OpenAI client instance.
    """
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def call_openai_chat(user_prompt: str, system_prompt: str = "") -> str:
    """Sends a chat message to the OpenAI API using the async client and
    retrieves the response.

    Args:
        user_prompt (str): The message from the user.
        system_prompt (str, optional): The system instruction (contextual guidance). Defaults to "".

    Returns:
        str: The assistant's response text, or an empty string on error.
    """
    client = get_async_client()
    try:
        response = await client.chat.completions.create(...)
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.exception(f"OpenAI API error: {e}")
        return ""
