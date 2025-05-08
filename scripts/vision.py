# This module handles uploading images and sending them to GPT-4 Vision.
# It extracts object tags and stores them for future search in the inventory app.


import base64
import logging
import os

import openai
from openai import AsyncOpenAI, OpenAI


def encode_image_to_base64(image_path: str) -> str:
    """
    Opens an image and returns its base64-encoded string.
    """
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# TODO: Send a base64 image to OpenAI's Vision API and parse the tags
def analyze_image_with_openai(image_path: str) -> dict:
    """
    Sends the image to OpenAI Vision and returns a list of extracted tags.
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
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                    },
                ],
            }
        ],
        max_tokens=500,
    )

    content = response.choices[0].message.content
    print(content)
    return {"summary": content}


def get_async_client():
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def call_openai_chat(user_prompt: str, system_prompt: str = "") -> str:
    client = get_async_client()
    try:
        response = await client.chat.completions.create(...)
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.exception(f"OpenAI API error: {e}")
        return ""
