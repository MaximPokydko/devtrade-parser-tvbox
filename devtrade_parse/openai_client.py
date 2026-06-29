"""Единый ленивый OpenAI-клиент на весь модуль (чтобы не плодить экземпляры)."""

from openai import OpenAI

from . import config

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        kwargs = {}
        if config.FORCE_IPV4:
            # Кривой IPv6 на tvbox: биндим httpx на IPv4 (как curl -4).
            import httpx

            kwargs["http_client"] = httpx.Client(
                transport=httpx.HTTPTransport(local_address="0.0.0.0")
            )
        _client = OpenAI(**kwargs)
    return _client
