import re


def clean_tag_name(tag: str) -> str:
    """
    Normalize a tag by:
    - Lowercasing
    - Stripping whitespace
    - Removing surrounding quotes or commas
    - Removing non-alphanumeric characters (except dashes and underscores)
    """
    tag = tag.strip().lower()
    tag = tag.strip("\"',")  # outer quotes
    tag = re.sub(r"[^\w\- ]", "", tag)  # remove unwanted symbols
    tag = re.sub(r"\s+", " ", tag)  # collapse multiple spaces
    return tag.strip()
