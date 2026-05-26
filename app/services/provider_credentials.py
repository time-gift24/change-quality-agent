from dataclasses import dataclass


@dataclass(frozen=True)
class PreparedApiKey:
    ciphertext: str
    hint: str


def api_key_hint(api_key: str) -> str:
    if len(api_key) < 8:
        return "********"
    return f"{api_key[:3]}...{api_key[-4:]}"


def prepare_api_key(api_key: str) -> PreparedApiKey:
    return PreparedApiKey(
        ciphertext=api_key,
        hint=api_key_hint(api_key),
    )
