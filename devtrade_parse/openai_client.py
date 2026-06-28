"""Единый ленивый OpenAI-клиент на весь модуль (чтобы не плодить экземпляры)."""

from openai import OpenAI

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client
