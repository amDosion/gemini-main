from google import genai
from app.core.config import settings

_vertex_client = None
_dev_client = None


def get_vertex_client() -> genai.Client:
    global _vertex_client
    if _vertex_client is not None:
        return _vertex_client

    if not settings.project:
        raise RuntimeError("Missing GOOGLE_CLOUD_PROJECT")
    if not settings.location:
        raise RuntimeError("Missing GOOGLE_CLOUD_LOCATION")

    _vertex_client = genai.Client(
        vertexai=True,
        project=settings.project,
        location=settings.location,
    )
    return _vertex_client


def get_developer_client() -> genai.Client:
    global _dev_client
    if _dev_client is not None:
        return _dev_client

    if not settings.gemini_api_key:
        raise RuntimeError("Missing GEMINI_API_KEY / GOOGLE_API_KEY")

    _dev_client = genai.Client(api_key=settings.gemini_api_key)
    return _dev_client
