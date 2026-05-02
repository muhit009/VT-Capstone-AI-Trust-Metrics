"""
chat_client.py — Generic OpenAI-compatible chat completions client.

Works with any OpenAI-compatible /v1/chat/completions endpoint:
    - NVIDIA NIM  (cloud deployment, no VPN needed)
    - VT ARC llm-api.arc.vt.edu (on VPN)
    - Groq, Together AI, etc.

Configure via environment variables (see root config.py):
    CHAT_BASE_URL  e.g. https://integrate.api.nvidia.com/v1
    CHAT_API_KEY   Bearer token
    CHAT_MODEL     e.g. mistralai/mistral-large-3-675b-instruct-2512
"""
from __future__ import annotations

import logging
import os
import time

import requests
from typing import TypedDict

from .config import (
    CHAT_BASE_URL as _CHAT_BASE_URL,
    CHAT_API_KEY  as _CHAT_API_KEY,
    CHAT_MODEL,
    CHAT_TIMEOUT,
    CHAT_OPTIONS,
    CHAT_RETRY_ATTEMPTS,
    CHAT_RETRY_DELAY,
)

logger = logging.getLogger(__name__)

CHAT_BASE_URL = os.environ.get("CHAT_BASE_URL", _CHAT_BASE_URL)
CHAT_API_KEY  = os.environ.get("CHAT_API_KEY",  _CHAT_API_KEY)


class ChatResult(TypedDict):
    answer:   str
    logprobs: list[float]
    tokens:   list[str]
    model:    str


def _parse_prompt(prompt: str) -> list[dict]:
    """
    Convert the rag_orchestrator prompt string into chat messages.

    The orchestrator produces strings in the form:
        SYSTEM: <system content>
        HUMAN: <user content>
    """
    if "\nHUMAN: " in prompt:
        parts          = prompt.split("\nHUMAN: ", 1)
        system_content = parts[0].removeprefix("SYSTEM: ").strip()
        user_content   = parts[1].strip()
        return [
            {"role": "system", "content": system_content},
            {"role": "user",   "content": user_content},
        ]
    return [{"role": "user", "content": prompt.strip()}]


def generate(
    prompt:  str,
    model:   str = CHAT_MODEL,
    options: dict | None = None,
) -> ChatResult:
    """
    Call an OpenAI-compatible /chat/completions endpoint with logprobs.

    Parameters
    ----------
    prompt  : Full prompt string from rag_orchestrator (SYSTEM: ... HUMAN: ...).
    model   : Model name registered with the provider.
    options : Generation options; merged over defaults.

    Returns
    -------
    ChatResult with answer text, log-probabilities, and token strings.

    Raises
    ------
    RuntimeError if the API is unreachable after all retries or returns non-200.
    """
    merged   = {**CHAT_OPTIONS, **(options or {})}
    messages = _parse_prompt(prompt)

    payload = {
        "model":        model,
        "messages":     messages,
        "max_tokens":   merged.get("max_tokens", 512),
        "temperature":  merged.get("temperature", 0),
        "logprobs":     True,
        "top_logprobs": 1,
    }

    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {CHAT_API_KEY}",
    }

    last_error = None
    for attempt in range(1, CHAT_RETRY_ATTEMPTS + 1):
        try:
            logger.debug("chat_client generate attempt %d/%d", attempt, CHAT_RETRY_ATTEMPTS)
            resp = requests.post(
                f"{CHAT_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                timeout=CHAT_TIMEOUT,
            )

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Chat API returned HTTP {resp.status_code}: {resp.text[:300]}"
                )

            data   = resp.json()
            choice = data["choices"][0]
            answer = choice["message"]["content"]

            logprobs: list[float] = []
            tokens:   list[str]   = []

            raw = choice.get("logprobs")
            if raw and raw.get("content"):
                for entry in raw["content"]:
                    lp = entry.get("logprob")
                    if lp is not None:
                        logprobs.append(lp)
                        tokens.append(entry.get("token", ""))

            logger.info(
                "chat_client generate OK: %d tokens, answer length %d chars",
                len(tokens), len(answer),
            )

            return ChatResult(
                answer=answer,
                logprobs=logprobs,
                tokens=tokens,
                model=data.get("model", model),
            )

        except requests.exceptions.ConnectionError as e:
            last_error = e
            logger.warning(
                "Chat API connection failed (attempt %d/%d): %s",
                attempt, CHAT_RETRY_ATTEMPTS, e,
            )
            if attempt < CHAT_RETRY_ATTEMPTS:
                time.sleep(CHAT_RETRY_DELAY)

    raise RuntimeError(
        f"Cannot reach chat API at {CHAT_BASE_URL} after {CHAT_RETRY_ATTEMPTS} attempts."
    )


def health_check() -> bool:
    """Return True if the chat API endpoint is reachable."""
    try:
        resp = requests.get(
            f"{CHAT_BASE_URL}/models",
            headers={"Authorization": f"Bearer {CHAT_API_KEY}"},
            timeout=5,
        )
        return resp.status_code == 200
    except requests.exceptions.RequestException:
        return False
