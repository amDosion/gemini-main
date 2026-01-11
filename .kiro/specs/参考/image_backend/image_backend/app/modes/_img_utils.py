import base64

def b64_to_bytes(b64_str: str) -> bytes:
    return base64.b64decode("".join(b64_str.strip().split()))

def bytes_to_b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("utf-8")
