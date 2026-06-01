from dataclasses import dataclass

from app.routers.core.modes import _media_metadata_from_payload
from app.utils.message_assembly import assemble_messages_v3
from app.utils.message_utils import extract_metadata


def test_media_metadata_extracts_openai_response_id_from_image_payload() -> None:
    metadata = _media_metadata_from_payload(
        {
            "images": [
                {
                    "url": "/api/storage/local-files/result.png",
                    "openai_response_id": "resp_image_123",
                }
            ]
        }
    )

    assert metadata["openai_response_id"] == "resp_image_123"


def test_extract_metadata_preserves_openai_response_id_from_attachment() -> None:
    metadata = extract_metadata(
        {
            "id": "msg-1",
            "attachments": [
                {
                    "id": "att-1",
                    "openaiResponseId": "resp_attachment_123",
                }
            ],
        }
    )

    assert metadata["openai_response_id"] == "resp_attachment_123"


@dataclass
class _Index:
    id: str
    table_name: str
    mode: str


class _Message:
    def __init__(self, payload):
        self.payload = payload

    def to_dict(self):
        return dict(self.payload)


class _Attachment:
    def __init__(self, payload):
        self.payload = payload

    def to_dict(self):
        return dict(self.payload)


def test_assemble_messages_backfills_openai_response_id_onto_attachments() -> None:
    assembled = assemble_messages_v3(
        "session-1",
        [_Index(id="msg-1", table_name="messages_image_chat_edit", mode="image-chat-edit")],
        {
            "messages_image_chat_edit": {
                "msg-1": _Message(
                    {
                        "id": "msg-1",
                        "role": "model",
                        "content": "done",
                        "timestamp": 1,
                        "openai_response_id": "resp_model_123",
                    }
                )
            }
        },
        {
            "msg-1": [
                _Attachment(
                    {
                        "id": "att-1",
                        "mime_type": "image/png",
                        "url": "/api/storage/local-files/result.png",
                    }
                )
            ]
        },
    )

    assert assembled[0]["attachments"][0]["openai_response_id"] == "resp_model_123"
