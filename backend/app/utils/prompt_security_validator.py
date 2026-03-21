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
    
    SENSITIVE_PATTERNS = {
        'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        'api_key': r'\b[A-Za-z0-9]{32,}\b'
    }
    
    MAX_LENGTH = 10000
    MIN_LENGTH = 10
    
    def validate_prompt(self, prompt: str) -> Tuple[bool, List[str]]:
        """Validate prompt security"""
        warnings = []
        
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
        
        return True, []
