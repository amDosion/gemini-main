"""
数据脱敏工具

用于脱敏敏感信息，保护用户隐私。
"""
import re
from typing import Optional


class DataMasker:
    """数据脱敏器"""
    
    # 正则表达式模式
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    PHONE_PATTERN = re.compile(r'\b(?:\+?86)?1[3-9]\d{9}\b')
    CREDIT_CARD_PATTERN = re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')
    ID_CARD_PATTERN = re.compile(r'\b\d{17}[\dXx]\b')
    
    @staticmethod
    def mask_email(text: str) -> str:
        """
        脱敏邮箱地址
        
        示例: user@example.com -> u***@example.com
        """
        def replacer(match):
            email = match.group(0)
            parts = email.split('@')
            if len(parts) != 2:
                return email
            
            username = parts[0]
            domain = parts[1]
            
            if len(username) <= 2:
                masked_username = username[0] + '*'
            else:
                masked_username = username[0] + '*' * (len(username) - 1)
            
            return f"{masked_username}@{domain}"
        
        return DataMasker.EMAIL_PATTERN.sub(replacer, text)
    
    @staticmethod
    def mask_phone(text: str) -> str:
        """
        脱敏电话号码
        
        示例: 13812345678 -> 138****5678
        """
        def replacer(match):
            phone = match.group(0)
            # 移除可能的 +86 前缀
            phone = phone.replace('+86', '').replace('+', '')
            
            if len(phone) == 11:
                return phone[:3] + '****' + phone[-4:]
            return phone
        
        return DataMasker.PHONE_PATTERN.sub(replacer, text)
    
    @staticmethod
    def mask_credit_card(text: str) -> str:
        """
        脱敏信用卡号
        
        示例: 1234 5678 9012 3456 -> **** **** **** 3456
        """
        def replacer(match):
            card = match.group(0)
            # 移除空格和连字符
            card_digits = card.replace(' ', '').replace('-', '')
            
            if len(card_digits) == 16:
                # 保留最后4位
                masked = '**** **** **** ' + card_digits[-4:]
                return masked
            return card
        
        return DataMasker.CREDIT_CARD_PATTERN.sub(replacer, text)
    
    @staticmethod
    def mask_id_card(text: str) -> str:
        """
        脱敏身份证号
        
        示例: 110101199001011234 -> 110101********1234
        """
        def replacer(match):
            id_card = match.group(0)
            
            if len(id_card) == 18:
                return id_card[:6] + '********' + id_card[-4:]
            return id_card
        
        return DataMasker.ID_CARD_PATTERN.sub(replacer, text)
    
    @staticmethod
    def mask_all(text: str) -> str:
        """
        脱敏所有敏感信息
        
        Args:
            text: 原始文本
            
        Returns:
            脱敏后的文本
        """
        if not text:
            return text
        
        # 按顺序应用所有脱敏规则
        text = DataMasker.mask_email(text)
        text = DataMasker.mask_phone(text)
        text = DataMasker.mask_credit_card(text)
        text = DataMasker.mask_id_card(text)
        
        return text
