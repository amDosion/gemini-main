from typing import Tuple
import google.auth
from google.auth.transport.requests import Request

_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)

def get_adc_token() -> Tuple[str, str]:
    creds, project_id = google.auth.default(scopes=_SCOPES)
    creds.refresh(Request())
    return creds.token, (project_id or "")
