from app.services.agent.workflow_payload_normalizer import (
    _normalize_workflow_nodes,
    _validate_and_normalize_agent_card,
)


def test_workflow_video_resolution_uses_official_runtime_tokens() -> None:
    [node] = _normalize_workflow_nodes(
        [
            {
                "id": "video-agent",
                "type": "agent",
                "data": {
                    "type": "agent",
                    "agentTaskType": "video-gen",
                    "agentResolutionTier": "4K",
                },
            }
        ]
    )

    assert node["data"]["agentResolutionTier"] == "4k"


def test_workflow_video_mask_mode_keeps_official_edit_modes() -> None:
    [node] = _normalize_workflow_nodes(
        [
            {
                "id": "video-agent",
                "type": "agent",
                "data": {
                    "type": "agent",
                    "agentTaskType": "video-gen",
                    "agentVideoMaskMode": "remove-static",
                },
            }
        ]
    )

    assert node["data"]["agentVideoMaskMode"] == "REMOVE_STATIC"


def test_agent_card_normalizes_image_edit_defaults_used_by_template_agents() -> None:
    card = _validate_and_normalize_agent_card(
        {
            "defaults": {
                "defaultTaskType": "image-edit",
                "imageEdit": {
                    "editMode": "chat-edit",
                    "imageSize": "1K",
                    "resolutionTier": "1K",
                    "numberOfImages": "9",
                    "outputMimeType": "IMAGE/PNG",
                    "promptExtend": "true",
                    "addMagicSuffix": "false",
                    "preserveProductIdentity": "yes",
                    "productMatchThreshold": "120",
                    "maxRetries": "8",
                    "outputLanguage": " en ",
                },
            }
        }
    )

    assert card["defaults"]["imageEdit"] == {
        "editMode": "image-chat-edit",
        "imageSize": "1K",
        "resolutionTier": "1K",
        "numberOfImages": 8,
        "outputMimeType": "image/png",
        "promptExtend": True,
        "addMagicSuffix": False,
        "preserveProductIdentity": True,
        "productMatchThreshold": 95,
        "maxRetries": 3,
        "outputLanguage": "en",
    }


def test_agent_card_normalizes_advanced_video_defaults_used_by_template_agents() -> None:
    card = _validate_and_normalize_agent_card(
        {
            "defaults": {
                "defaultTaskType": "video-gen",
                "videoGeneration": {
                    "aspectRatio": "16:9",
                    "resolution": "2K",
                    "durationSeconds": "8",
                    "videoExtensionCount": "4",
                    "continueFromPreviousVideo": "0",
                    "continueFromPreviousLastFrame": "true",
                    "generateAudio": "yes",
                    "subtitleMode": "srt",
                    "subtitleLanguage": " zh-CN ",
                    "subtitleScript": "line 1",
                    "storyboardPrompt": "shot 1",
                    "negativePrompt": "no blur",
                    "seed": "42",
                    "promptExtend": "true",
                },
            }
        }
    )

    assert card["defaults"]["videoGeneration"] == {
        "aspectRatio": "16:9",
        "resolution": "1080p",
        "durationSeconds": 8,
        "videoExtensionCount": 4,
        "continueFromPreviousVideo": False,
        "continueFromPreviousLastFrame": True,
        "generateAudio": True,
        "subtitleMode": "srt",
        "subtitleLanguage": "zh-CN",
        "subtitleScript": "line 1",
        "storyboardPrompt": "shot 1",
        "negativePrompt": "no blur",
        "seed": 42,
        "promptExtend": True,
    }
