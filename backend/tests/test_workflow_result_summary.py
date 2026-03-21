from app.routers.ai.workflows import _build_workflow_result_summary


def test_workflow_result_summary_extracts_video_extension_and_subtitle_metadata() -> None:
    summary = _build_workflow_result_summary(
        {
            "finalOutput": {
                "url": "/api/temp-images/video-1",
                "mime_type": "video/mp4",
                "continuation_strategy": "video_extension_chain",
                "video_extension_count": 3,
                "video_extension_applied": 3,
                "total_duration_seconds": 29,
                "continued_from_video": True,
                "subtitle_mode": "vtt",
                "sidecar_files": [
                    {
                        "url": "/api/temp-images/subtitle-1",
                        "mime_type": "text/vtt",
                        "format": "vtt",
                    }
                ],
            }
        }
    )

    assert summary["video_count"] == 1
    assert summary["continuation_strategy"] == "video_extension_chain"
    assert summary["video_extension_count"] == 3
    assert summary["video_extension_applied"] == 3
    assert summary["total_duration_seconds"] == 29
    assert summary["continued_from_video"] is True
    assert summary["subtitle_mode"] == "vtt"
    assert summary["subtitle_file_count"] == 1


def test_workflow_result_summary_prefers_final_node_video_metadata_over_inputs() -> None:
    summary = _build_workflow_result_summary(
        {
            "finalNodeId": "end-video",
            "outputs": {
                "input-video": {
                    "url": "/api/temp-images/source-video",
                    "mime_type": "video/mp4",
                    "continued_from_video": False,
                },
                "end-video": {
                    "url": "/api/temp-images/output-video",
                    "mime_type": "video/mp4",
                    "video_extension_applied": 1,
                    "total_duration_seconds": 15,
                    "subtitle_mode": "none",
                },
            },
        }
    )

    assert summary["video_count"] == 1
    assert summary["video_extension_applied"] == 1
    assert summary["total_duration_seconds"] == 15
    assert summary["continued_from_video"] is False
    assert summary["subtitle_mode"] == "none"
