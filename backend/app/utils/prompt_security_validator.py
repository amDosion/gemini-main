import re
from typing import Tuple, List


class PromptSecurityValidator:
    """Prompt security validator"""

    DANGEROUS_KEYWORDS = [
        'ignore previous instructions',
        'ignore all previous',
        'disregard previous',
        'forget everything',
        'new instructions',
        'system prompt',
        'you are now',
        'act as if',
        'pretend you are',
        'roleplay as'
    ]

    # Hard-block patterns: definitive PII that should never appear in prompts.
    SENSITIVE_PATTERNS = {
        'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    }

    # Advisory-only patterns: well-known credential prefixes that are heuristic
    # and may produce false positives (e.g., a UUID or token that happens to
    # match the prefix).  These are returned as warnings but do NOT hard-block
    # the request so that legitimate prompts about API design are not rejected.
    #
    # Trade-off: an attacker who knows these prefixes can trivially avoid them;
    # the purpose is accidental-exposure detection, not adversarial prevention.
    ADVISORY_PATTERNS = {
        'openai_api_key': r'\bsk-[A-Za-z0-9]{48}\b',
        'google_api_key': r'\bAIza[A-Za-z0-9_-]{35}\b',
    }

    MAX_LENGTH = 10000
    MIN_LENGTH = 10

    def validate_prompt(self, prompt: str) -> Tuple[bool, List[str]]:
        """Validate prompt security.

        Returns:
            (is_safe, warnings) where is_safe=False blocks the request.
            Advisory-only matches populate warnings but keep is_safe=True.
        """
        warnings: List[str] = []

        if len(prompt) < self.MIN_LENGTH:
            warnings.append(f"Prompt too short (min {self.MIN_LENGTH} characters)")
            return False, warnings

        if len(prompt) > self.MAX_LENGTH:
            warnings.append(f"Prompt too long (max {self.MAX_LENGTH} characters)")
            return False, warnings

        prompt_lower = prompt.lower()
        for keyword in self.DANGEROUS_KEYWORDS:
            if keyword in prompt_lower:
                warnings.append(f"Dangerous keyword detected: {keyword}")
                return False, warnings

        for pattern_name, pattern in self.SENSITIVE_PATTERNS.items():
            if re.search(pattern, prompt):
                warnings.append(f"Sensitive information detected: {pattern_name}")

        if warnings:
            return False, warnings

        # Advisory patterns: accumulate warnings but do not block.
        advisory_warnings: List[str] = []
        for pattern_name, pattern in self.ADVISORY_PATTERNS.items():
            if re.search(pattern, prompt):
                advisory_warnings.append(
                    f"Possible credential pattern detected: {pattern_name}"
                )

        return True, advisory_warnings
