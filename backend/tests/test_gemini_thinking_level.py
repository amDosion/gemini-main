from app.services.gemini.common.config_builder import ConfigBuilder


def test_gemini_generate_config_applies_thinking_level() -> None:
    config = ConfigBuilder.build_generate_config_with_tools(
        enable_thinking=True,
        thinking_level="high",
    )

    assert config.thinking_config is not None
    assert config.thinking_config.include_thoughts is True
    assert config.thinking_config.thinking_level.value == "HIGH"
