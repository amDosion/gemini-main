import pytest

from app.services.gemini.common.file_handler import FileHandler


def test_create_file_part_accepts_provider_file_references():
    handler = FileHandler()

    assert handler.create_file_part(" files/abc123 ", "image/png") == {
        "file_data": {
            "file_uri": "files/abc123",
            "mime_type": "image/png",
        }
    }
    assert handler.create_file_part("gs://bucket/object.png") == {
        "file_data": {"file_uri": "gs://bucket/object.png"}
    }
    assert handler.create_file_part("https://generativelanguage.googleapis.com/v1beta/files/abc") == {
        "file_data": {
            "file_uri": "https://generativelanguage.googleapis.com/v1beta/files/abc"
        }
    }


@pytest.mark.parametrize(
    "file_uri",
    [
        "",
        "file:///etc/passwd",
        "/etc/passwd",
        r"C:\Users\secret\image.png",
        "https://example.com/not-a-provider-file",
    ],
)
def test_create_file_part_rejects_unsupported_file_references(file_uri):
    handler = FileHandler()

    with pytest.raises(ValueError, match="Unsupported Gemini file URI"):
        handler.create_file_part(file_uri)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "file_name",
    [
        "",
        "gs://bucket/object.png",
        "file:///etc/passwd",
        r"C:\Users\secret\image.png",
        "https://generativelanguage.googleapis.com/v1beta/files/abc",
    ],
)
async def test_file_api_methods_reject_non_file_names_before_sdk_call(file_name):
    handler = FileHandler()

    with pytest.raises(ValueError, match="files/... provider format"):
        await handler.get_file_info(file_name)

    with pytest.raises(ValueError, match="files/... provider format"):
        await handler.download_file(file_name)

    with pytest.raises(ValueError, match="files/... provider format"):
        await handler.delete_file(file_name)
