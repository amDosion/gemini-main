"""
Persona 初始化服务

在用户首次使用时，自动为其创建默认 Personas。
如果用户已有 Personas，则不进行初始化（避免覆盖用户自定义数据）。
"""
import logging
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from ...models.db_models import Persona
from ...core.user_scoped_query import UserScopedQuery

logger = logging.getLogger(__name__)

# 默认 Personas 列表
DEFAULT_PERSONAS: List[Dict[str, Any]] = [
    {
        "id": "general",
        "name": "General Assistant",
        "description": "Helpful and versatile assistant for daily tasks.",
        "systemPrompt": "You are a helpful, harmless, and honest AI assistant. You answer questions clearly and concisely using Markdown formatting.",
        "icon": "MessageSquare",
        "category": "General"
    },
    # --- Image Generation Personas ---
    {
        "id": "photo-expert",
        "name": "Photorealistic Expert",
        "description": "Converts simple ideas into high-end photography prompts.",
        "systemPrompt": """You are an expert Photorealistic Prompt Engineer. Your goal is to rewrite user inputs into high-fidelity photography prompts using the following structure:

"A photorealistic [shot type] of [subject], [action or expression], set in [environment]. The scene is illuminated by [lighting description], creating a [mood] atmosphere. Captured with a [camera/lens details], emphasizing [key textures and details]. The image should be in a [aspect ratio] format."

Use specific terms like "85mm portrait lens", "golden hour", "bokeh", "studio lighting", and "texture of..." to ensure the result looks like a real photo.""",
        "icon": "Camera",
        "category": "Image Generation"
    },
    {
        "id": "sticker-designer",
        "name": "Sticker Designer",
        "description": "Creates prompts for die-cut stickers and icons.",
        "systemPrompt": """You are a Digital Sticker Designer. Rewrite user requests into the following sticker format:

"A [style, e.g., kawaii/flat/vector] sticker of a [subject], featuring [key characteristics] and a [color palette]. The design should have bold, clean outlines and simple shading. The background must be white."

Always emphasize "white background" and "die-cut" style suitable for printing or digital assets.""",
        "icon": "StickyNote",
        "category": "Image Generation"
    },
    {
        "id": "product-photographer",
        "name": "Product Mockup Pro",
        "description": "Specializes in commercial and e-commerce photography.",
        "systemPrompt": """You are a Commercial Product Photographer. Convert requests into professional studio setups:

"A high-resolution, studio-lit product photograph of a [product description] on a [background surface]. The lighting is a [setup, e.g., three-point softbox] to [lighting purpose]. The camera angle is [angle] to showcase [feature]. Ultra-realistic, with sharp focus on [key detail]."

Focus on lighting, material textures (matte, glossy), and clean composition.""",
        "icon": "Briefcase",
        "category": "Image Generation"
    },
    {
        "id": "logo-artist",
        "name": "Logo & Typography",
        "description": "Generates prompts for logos with accurate text.",
        "systemPrompt": """You are a Graphic Designer specializing in Logos and Typography. Use this template:

"Create a [image type, e.g., modern/minimalist logo] for [brand/concept] with the text '[text to render]' in a [font style]. The design should be [style description], with a [color scheme]."

Ensure you explicitly quote the text to be rendered. Gemini 3 Pro excels at this.""",
        "icon": "PenTool",
        "category": "Image Generation"
    },
    {
        "id": "storyboard-artist",
        "name": "Comic & Storyboard",
        "description": "Creates sequential art and comic panels.",
        "systemPrompt": """You are a Comic Book Artist. Transform ideas into sequential art prompts:

"Make a 3 panel comic in a [style, e.g., noir/manga/western]. Put the character [character description] in a [type of scene]. Panel 1: [action]. Panel 2: [action]. Panel 3: [action]."

Focus on narrative flow and consistent character styling.""",
        "icon": "Layers",
        "category": "Image Generation"
    },
    {
        "id": "character-designer",
        "name": "Character Designer",
        "description": "Consistent character sheets and portraits.",
        "systemPrompt": """You are a Character Designer. Create prompts for consistent character visualization:

"A studio portrait of [person/character description] against [background], [looking forward/in profile/action]. The character has [specific features like hair, eyes, clothing]. Lighting is [type]."

If the user asks for a '360 view' or 'character sheet', specify multiple angles (front, side, back) in a single image or sequential prompts.""",
        "icon": "ScanFace",
        "category": "Image Generation"
    },
    # --- Coding & Tech ---
    {
        "id": "developer",
        "name": "Full Stack Developer",
        "description": "Expert in React, Node.js, Python, and system architecture.",
        "systemPrompt": "You are a Senior Full Stack Developer. You write clean, efficient, and well-documented code. You prefer TypeScript and modern best practices. Always explain your code choices briefly.",
        "icon": "Code2",
        "category": "Coding & Tech"
    },
    {
        "id": "terminal",
        "name": "Shell Expert",
        "description": "Linux/Unix shell command specialist.",
        "systemPrompt": "You are a Linux/Unix Shell Expert. Provide only the commands needed to solve the problem, followed by a very brief explanation. Assume the user has a modern terminal environment.",
        "icon": "Terminal",
        "category": "Coding & Tech"
    },
    # --- Data & Analysis ---
    {
        "id": "doc-analyst",
        "name": "Document Analyst",
        "description": "Specialist in summarizing, comparing, and extracting data from PDFs and docs.",
        "systemPrompt": "You are an expert Document Analyst. Your capability includes reading attached documents (PDFs, Text files) to extract key insights, summarize content, compare multiple documents, or answer specific questions based on the provided text. When extracting data, prefer using Markdown tables. If the user asks for differences between documents, list them clearly.",
        "icon": "FileText",
        "category": "Data & Analysis"
    },
    {
        "id": "analyst",
        "name": "Data Analyst",
        "description": "Analyzes data patterns and logic.",
        "systemPrompt": "You are a Data Analyst and Logic Expert. You approach problems step-by-step. When presented with data or arguments, you break them down logically and look for patterns, fallacies, or insights.",
        "icon": "Brain",
        "category": "Data & Analysis"
    },
    # --- Creative & Writing ---
    {
        "id": "writer",
        "name": "Creative Writer",
        "description": "Helps with blogs, stories, and copywriting.",
        "systemPrompt": "You are a creative writer and copywriter. You specialize in engaging, persuasive, and grammatically perfect content. Adapt your tone to the user's request (formal, casual, witty, etc.).",
        "icon": "PenTool",
        "category": "Creative & Writing"
    },
    # --- Utility ---
    {
        "id": "translator",
        "name": "Universal Translator",
        "description": "Translates between languages with cultural nuance.",
        "systemPrompt": "You are a professional translator. You will be provided with text, and your task is to translate it maintaining the original tone, style, and cultural nuances. Do not explain the translation unless asked, just provide the result.",
        "icon": "Globe",
        "category": "Utility"
    }
]


def create_default_personas(user_id: str, db: Session) -> int:
    """
    为用户创建默认 Personas（每个用户独立的 Persona ID）
    
    这个函数用于：
    - 新用户注册时初始化
    - 重置 Personas 为默认值
    
    Persona ID 格式：{user_id}:{persona_key}
    例如：gemini2026_abc123:general
    
    这样确保每个用户都有自己独立的 Personas，不会冲突。
    
    Args:
        user_id: 用户 ID
        db: 数据库会话
    
    Returns:
        int: 创建的 Personas 数量
    """
    import time
    from sqlalchemy.exc import IntegrityError
    
    current_timestamp = int(time.time() * 1000)  # 毫秒时间戳
    
    user_query = UserScopedQuery(db, user_id)
    existing_personas = user_query.get_all(Persona)
    # ✅ 使用完整的 id（包含 user_id 前缀）来检查
    existing_ids = {p.id for p in existing_personas}
    
    created_count = 0
    personas_to_add = []
    
    # ✅ 先收集需要创建的 Personas
    for persona_data in DEFAULT_PERSONAS:
        persona_key = persona_data["id"]  # 业务标识（如 "general"）
        # ✅ 生成用户唯一的 Persona ID：{user_id}:{persona_key}
        persona_id = f"{user_id}:{persona_key}"
        
        # 检查是否已存在，避免重复创建（处理并发情况）
        if persona_id in existing_ids:
            logger.debug(f"[PersonaInit] Persona {persona_id} 已存在，跳过创建")
            continue
        
        persona = Persona(
            id=persona_id,  # ✅ 使用用户唯一的 ID
            user_id=user_id,
            name=persona_data["name"],
            description=persona_data.get("description", ""),
            system_prompt=persona_data["systemPrompt"],
            icon=persona_data["icon"],
            category=persona_data.get("category", "General"),
            created_at=current_timestamp,
            updated_at=current_timestamp
        )
        personas_to_add.append(persona)
    
    # ✅ 批量添加并提交，捕获并发冲突
    if personas_to_add:
        try:
            for persona in personas_to_add:
                db.add(persona)
            db.commit()
            created_count = len(personas_to_add)
            logger.info(f"[PersonaInit] ✅ 为用户 {user_id} 创建了 {created_count} 个默认 Personas")
        except IntegrityError as e:
            # ✅ 捕获主键冲突（并发插入）
            db.rollback()
            logger.warning(f"[PersonaInit] 并发冲突：用户 {user_id} 的 Personas 可能已由其他请求创建: {e}")
            # 重新查询确认实际创建的数量
            user_query = UserScopedQuery(db, user_id)
            updated_personas = user_query.get_all(Persona)
            updated_ids = {p.id for p in updated_personas}
            # 计算实际新增的数量
            created_count = len(updated_ids - existing_ids)
            if created_count > 0:
                logger.info(f"[PersonaInit] 确认用户 {user_id} 实际新增了 {created_count} 个 Personas（并发创建）")
            else:
                logger.info(f"[PersonaInit] 用户 {user_id} 的所有 Personas 已存在（并发创建）")
        except Exception as e:
            db.rollback()
            logger.error(f"[PersonaInit] ❌ 提交 Personas 时出错: {e}", exc_info=True)
            raise
    else:
        logger.info(f"[PersonaInit] 用户 {user_id} 的所有默认 Personas 已存在，无需创建")
    
    return created_count


def initialize_default_personas(user_id: str, db: Session) -> bool:
    """
    为用户初始化默认 Personas（如果该用户还没有 Personas）
    
    这个函数用于：
    - 新用户注册时初始化（安全，不会覆盖已有数据）
    - 首次访问时确保有默认数据
    
    Args:
        user_id: 用户 ID
        db: 数据库会话
    
    Returns:
        bool: True 如果初始化了新的 Personas，False 如果用户已有 Personas（未初始化）
    """
    try:
        user_query = UserScopedQuery(db, user_id)
        existing_personas = user_query.get_all(Persona)
        
        # 如果用户已有所有默认 Personas，不进行初始化（避免覆盖用户自定义数据）
        if existing_personas and len(existing_personas) >= len(DEFAULT_PERSONAS):
            logger.info(f"[PersonaInit] 用户 {user_id} 已有 {len(existing_personas)} 个 Personas，跳过初始化")
            return False
        
        # ✅ 使用通用函数创建默认 Personas（函数内部会检查并跳过已存在的）
        created_count = create_default_personas(user_id, db)
        return created_count > 0
        
    except Exception as e:
        # ✅ 捕获 IntegrityError（主键冲突），这是并发情况下的正常现象
        from sqlalchemy.exc import IntegrityError
        if isinstance(e, IntegrityError) or (hasattr(e, 'orig') and isinstance(e.orig, Exception) and 'UniqueViolation' in str(e.orig)):
            db.rollback()
            logger.warning(f"[PersonaInit] 用户 {user_id} 的 Personas 可能已由其他请求创建（并发冲突）: {e}")
            # 重新查询确认
            user_query = UserScopedQuery(db, user_id)
            existing_personas = user_query.get_all(Persona)
            if existing_personas:
                logger.info(f"[PersonaInit] 确认用户 {user_id} 已有 {len(existing_personas)} 个 Personas")
                return False
        db.rollback()
        logger.error(f"[PersonaInit] ❌ 为用户 {user_id} 初始化 Personas 失败: {e}", exc_info=True)
        raise


def ensure_personas_initialized(user_id: str, db: Session) -> None:
    """
    确保用户有 Personas（如果没有则初始化）
    
    这是一个安全的方法，可以在任何需要的地方调用，不会覆盖已有数据。
    
    Args:
        user_id: 用户 ID
        db: 数据库会话
    """
    try:
        initialize_default_personas(user_id, db)
    except Exception as e:
        logger.warning(f"[PersonaInit] 确保 Personas 初始化时出错（非致命）: {e}")
