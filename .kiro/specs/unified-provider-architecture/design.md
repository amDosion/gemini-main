# Unified Provider Client Architecture - Design Document

## Overview

This document describes the system-wide **unified provider client architecture**. In this project, the **backend is the single source of truth (SSOT)** for provider configuration, client creation, and capability/route selection. The frontend is a thin API client that consumes backend templates and routes requests through the backend.

**Key Innovation (backend)**: Each provider can support **dual-client mode**:
- **Primary Client**: Native SDK or advanced API (full feature access)
- **Secondary Client**: OpenAI-compatible API (fallback/compatibility)

This design is inspired by the existing backend implementation where Qwen and Ollama already use dual-client patterns.

## Scope & Ownership

- **Backend (SSOT)**: Provider configuration, ProviderClientFactory, dual-client selection, mode registries, capability detection.
- **Frontend (thin client)**: Provider template loading (`/api/providers/templates`), `UnifiedProviderClient`/`LLMFactory` routing, and UI/handler orchestration.
- **Exception (keep as-is)**: Tongyi remains mixed-mode for now (chat/models in backend; image generation still uses frontend proxy flow).

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Backend Provider Layer (SSOT)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │         Unified Provider Client Architecture (NEW)          │ │
│  │                                                              │ │
│  │  ┌────────────────────────────────────────────────────────┐│ │
│  │  │         ProviderClientFactory                           ││ │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐            ││ │
│  │  │  │  Google  │  │   Qwen   │  │  Ollama  │  ...       ││ │
│  │  │  │ Factory  │  │ Factory  │  │ Factory  │            ││ │
│  │  │  └──────────┘  └──────────┘  └──────────┘            ││ │
│  │  └────────────────────────────────────────────────────────┘│ │
│  │                                                              │ │
│  │  ┌────────────────────────────────────────────────────────┐│ │
│  │  │         Dual-Client Support                             ││ │
│  │  │  ┌─────────────────┐  ┌─────────────────┐             ││ │
│  │  │  │ Primary Client  │  │Secondary Client │             ││ │
│  │  │  │ (Native SDK)    │  │(OpenAI-compat)  │             ││ │
│  │  │  └─────────────────┘  └─────────────────┘             ││ │
│  │  └────────────────────────────────────────────────────────┘│ │
│  │                                                              │ │
│  │  ┌────────────────────────────────────────────────────────┐│ │
│  │  │         Provider Mode Registries                        ││ │
│  │  │  ┌──────────────┐  ┌──────────────┐                   ││ │
│  │  │  │   Google     │  │    Qwen      │  ...              ││ │
│  │  │  │ModeRegistry  │  │ModeRegistry  │                   ││ │
│  │  │  └──────────────┘  └──────────────┘                   ││ │
│  │  └────────────────────────────────────────────────────────┘│ │
│  │                                                              │ │
│  │  ┌────────────────────────────────────────────────────────┐│ │
│  │  │         Client Selection Strategy                       ││ │
│  │  │  selectClient(operation, capabilities, preferences)    ││ │
│  │  └────────────────────────────────────────────────────────┘│ │
│  │                                                              │ │
│  │  ┌────────────────────────────────────────────────────────┐│ │
│  │  │         Provider Configuration (YAML/JSON)              ││ │
│  │  │  - providerId, clientType, baseUrl                     ││ │
│  │  │  - primaryClient, secondaryClient                      ││ │
│  │  │  - capabilities, modes                                 ││ │
│  │  └────────────────────────────────────────────────────────┘│ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │         Generic Handler System (Existing - Unchanged)       │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐           │ │
│  │  │  OpenAI    │  │ DeepSeek   │  │   Other    │           │ │
│  │  │  Handler   │  │  Handler   │  │  Handlers  │           │ │
│  │  └────────────┘  └────────────┘  └────────────┘           │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

```
User Request
  ↓
Frontend Handler System (StrategyRegistry)
  ↓
UnifiedProviderClient (frontend)
  ↓
Backend API (/api/*)
  ↓
ProviderClientFactory.create(providerId, config)  // backend SSOT
  ↓
┌─────────────────────────────────────────┐
│ 1. Load Provider Configuration          │
│ 2. Detect Provider Capabilities         │
│ 3. Select Client (Primary/Secondary)    │
│ 4. Create/Cache Client Instance         │
│ 5. Get Mode Handler (if provider-specific)│
└─────────────────────────────────────────┘
  ↓
Execute Operation (Primary or Secondary Client)
  ↓
Response
```

## Core Components (Backend SSOT)

These components are implemented and owned by the backend. The frontend interacts with them only through backend APIs and does not instantiate provider SDKs directly.

**Note on Interface Languages**:
- **TypeScript interfaces**: Represent frontend API contracts and conceptual design
- **Python classes**: Actual backend implementation (SSOT)
- Both are provided for clarity, but Python implementation is authoritative

### 1. ProviderClientFactory

**Purpose**: Unified factory for creating provider client instances with dual-client support.

**TypeScript Interface** (Frontend API Contract):
```typescript
interface ProviderClientFactory {
  /**
   * Create a provider client instance
   * @param providerId - Provider identifier (e.g., 'google', 'qwen', 'ollama')
   * @param config - Provider configuration
   * @returns Provider client instance
   */
  create(providerId: string, config: ProviderConfig): ProviderClient;
  
  /**
   * Register a provider factory
   * @param providerId - Provider identifier
   * @param factory - Factory function
   */
  register(providerId: string, factory: ProviderFactoryFunction): void;
  
  /**
   * Get cached client instance
   * @param providerId - Provider identifier
   * @returns Cached client or null
   */
  getCached(providerId: string): ProviderClient | null;
}
```

**Python Class** (Backend Implementation):
```python
class ProviderFactory:
    """
    Factory class for creating AI provider service instances.
    Configuration-driven auto-registration based on ProviderConfig.
    """
    
    # Registry of provider names to service classes
    _providers: Dict[str, Type[BaseProviderService]] = {}
    _initialized: bool = False
    
    @classmethod
    def create(
        cls,
        provider: str,
        api_key: str,
        api_url: Optional[str] = None,
        user_id: Optional[str] = None,
        db: Optional[Session] = None,
        **kwargs
    ) -> BaseProviderService:
        """
        Create a provider service instance.
        
        Args:
            provider: Provider name (e.g., 'openai', 'google', 'ollama')
            api_key: API key for authentication
            api_url: Optional custom API URL (overrides config base_url)
            user_id: Optional user ID for user-specific configuration
            db: Optional database session for loading user config
            **kwargs: Additional configuration parameters
        
        Returns:
            Instance of the appropriate provider service class
        
        Raises:
            ValueError: If provider name is not registered
        """
        pass
    
    @classmethod
    def register(cls, provider_id: str, service_class: Type[BaseProviderService]) -> None:
        """Register a provider service class."""
        pass
    
    @classmethod
    def _auto_register(cls) -> None:
        """
        Automatically register providers based on ProviderConfig.
        Maps client_type to service classes:
        - client_type="openai": OpenAIService
        - client_type="google": GoogleService
        - client_type="ollama": OllamaService
        - client_type="dashscope": QwenNativeProvider
        """
        pass
```

**Implementation Pattern** (from backend):
```typescript
class ProviderClientFactory {
  private static providers: Map<string, ProviderFactoryFunction> = new Map();
  private static clientCache: Map<string, ProviderClient> = new Map();
  private static initialized = false;
  
  static create(providerId: string, config: ProviderConfig): ProviderClient {
    // Auto-register on first use
    if (!this.initialized) {
      this.autoRegister();
    }
    
    // Check cache
    const cacheKey = `${providerId}:${config.apiKey}`;
    if (this.clientCache.has(cacheKey)) {
      return this.clientCache.get(cacheKey)!;
    }
    
    // Create new client
    const factory = this.providers.get(providerId);
    if (!factory) {
      throw new Error(`Unknown provider: ${providerId}`);
    }
    
    const client = factory(config);
    this.clientCache.set(cacheKey, client);
    return client;
  }
  
  private static autoRegister(): void {
    // Iterate through provider configuration
    for (const [providerId, providerConfig] of Object.entries(PROVIDER_CONFIGS)) {
      const clientType = providerConfig.clientType;
      
      // Map client_type to factory function
      const factory = this.getFactoryForClientType(clientType);
      this.register(providerId, factory);
    }
    
    this.initialized = true;
  }
}
```

### 2. Dual-Client Architecture

**Purpose**: Support both native SDK and OpenAI-compatible API for each provider.

**TypeScript Interface** (Conceptual):
```typescript
interface DualClientProvider {
  primaryClient: NativeClient;      // Native SDK (full features)
  secondaryClient?: OpenAIClient;   // OpenAI-compatible (fallback)
  
  /**
   * Select which client to use for an operation
   */
  selectClient(operation: OperationType): 'primary' | 'secondary';
  
  /**
   * Execute operation with automatic client selection
   */
  execute(operation: Operation): Promise<Response>;
}
```

**Python Protocol** (Backend Implementation):
```python
from typing import Protocol, Optional, Literal, Any, Dict
from abc import abstractmethod

class DualClientProvider(Protocol):
    """
    Protocol for providers supporting dual-client architecture.
    Primary client (native SDK) + Secondary client (OpenAI-compatible).
    """
    
    primary_client: Any  # Native SDK client
    secondary_client: Optional[Any]  # OpenAI-compatible client
    
    def select_client(self, operation: Dict[str, Any]) -> Literal['primary', 'secondary']:
        """
        Select which client to use for an operation.
        
        Args:
            operation: Operation details (type, parameters, capabilities required)
        
        Returns:
            'primary' or 'secondary'
        """
        ...
    
    async def execute(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute operation with automatic client selection.
        
        Args:
            operation: Operation to execute
        
        Returns:
            Response in ChatResponse format
        """
        ...
```

**Example: Google Provider**:
```typescript
class GoogleDualClientProvider implements DualClientProvider {
  primaryClient: GoogleGenAIClient;     // Vertex AI or Developer API
  secondaryClient?: OpenAIClient;       // OpenAI-compatible endpoint
  
  constructor(config: GoogleProviderConfig) {
    // Primary: Native Google SDK
    this.primaryClient = new GoogleGenAIClient({
      apiKey: config.apiKey,
      platform: config.platform, // 'vertex' or 'developer'
    });
    
    // Secondary: OpenAI-compatible (if configured)
    if (config.secondaryBaseUrl) {
      this.secondaryClient = new OpenAIClient({
        apiKey: config.apiKey,
        baseURL: config.secondaryBaseUrl,
      });
    }
  }
  
  selectClient(operation: OperationType): 'primary' | 'secondary' {
    // Use primary for advanced features
    if (operation.requiresAdvancedFeatures) {
      return 'primary';
    }
    
    // Use secondary for basic chat (if available)
    if (this.secondaryClient && operation.type === 'chat') {
      return 'secondary';
    }
    
    return 'primary';
  }
}
```

**Example: Qwen Provider** (Backend Implementation):
```python
class QwenNativeProvider(BaseProviderService):
    """
    Qwen provider with dual-client support.
    Primary: DashScope native SDK (100% feature access)
    Secondary: OpenAI-compatible API (basic chat)
    """
    
    def __init__(self, api_key: str, api_url: Optional[str] = None, **kwargs):
        super().__init__(api_key, api_url, **kwargs)
        
        # Primary: DashScope native SDK
        dashscope.api_key = api_key
        self.primary_client = dashscope  # Native SDK
        
        # Secondary: OpenAI-compatible API
        self.secondary_client = AsyncOpenAI(
            api_key=api_key,
            base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'
        )
    
    def select_client(self, operation: Dict[str, Any]) -> Literal['primary', 'secondary']:
        """Select client based on operation requirements."""
        # Use primary for advanced features
        if operation.get('enable_search') or operation.get('plugins') or operation.get('enable_thinking'):
            return 'primary'
        
        # Use secondary for basic chat
        return 'secondary'
    
    async def chat(self, messages: List[Dict[str, Any]], model: str, **kwargs) -> Dict[str, Any]:
        """Execute chat with automatic client selection."""
        operation = {'type': 'chat', 'messages': messages, 'model': model, **kwargs}
        client_type = self.select_client(operation)
        
        if client_type == 'primary':
            # Use DashScope native SDK
            response = await asyncio.to_thread(
                Generation.call,
                model=model,
                messages=messages,
                **kwargs
            )
            return self._format_response(response)
        else:
            # Use OpenAI-compatible API
            response = await self.secondary_client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            return self._format_openai_response(response)
```

**Example: Ollama Provider** (Backend Implementation):
```python
class OllamaService(BaseProviderService):
    """
    Ollama provider with dual-API support.
    Primary: OpenAI-compatible API (/v1/*) for chat
    Secondary: Native Ollama API (/api/*) for advanced features
    """
    
    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_NATIVE_BASE_URL = "http://localhost:11434"
    
    def __init__(self, api_key: str = "ollama", api_url: Optional[str] = None, **kwargs):
        super().__init__(api_key, api_url, **kwargs)
        
        # Primary: OpenAI-compatible API
        openai_base_url = api_url or self.DEFAULT_BASE_URL
        self.primary_client = AsyncOpenAI(
            api_key=api_key,
            base_url=openai_base_url
        )
        
        # Secondary: Native Ollama API
        native_base_url = api_url.replace('/v1', '') if api_url else self.DEFAULT_NATIVE_BASE_URL
        self.secondary_client = httpx.AsyncClient(base_url=native_base_url)
        
        # Model info cache (TTL: 1 hour)
        self._model_cache: TTLCache = TTLCache(maxsize=100, ttl=3600)
    
    def select_client(self, operation: Dict[str, Any]) -> Literal['primary', 'secondary']:
        """Select client based on operation type."""
        operation_type = operation.get('type')
        
        # Use secondary for model management, embedding, capability detection
        if operation_type in ['modelList', 'modelInfo', 'embedding', 'capabilities']:
            return 'secondary'
        
        # Use primary for chat
        return 'primary'
    
    async def chat(self, messages: List[Dict[str, Any]], model: str, **kwargs) -> Dict[str, Any]:
        """Execute chat using OpenAI-compatible API."""
        response = await self.primary_client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs
        )
        return self._format_response(response)
    
    async def get_model_info(self, model: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Get model info using native Ollama API."""
        if not force_refresh and model in self._model_cache:
            return self._model_cache[model]
        
        response = await self.secondary_client.post(
            '/api/show',
            json={'name': model}
        )
        model_info = response.json()
        self._model_cache[model] = model_info
        return model_info
```

### 3. Provider Mode Registry

**Purpose**: Provider-specific mode handlers for custom operations (e.g., Google image editing modes).

**TypeScript Interface** (Conceptual):
```typescript
interface ProviderModeRegistry {
  /**
   * Register a mode handler
   */
  register(modeId: string, handler: ModeHandler): void;
  
  /**
   * Get mode handler
   */
  get(modeId: string): ModeHandler | null;
  
  /**
   * List all registered modes
   */
  listModes(): string[];
}
```

**Python Class** (Backend Implementation):
```python
from typing import Dict, Callable, Optional, List, Any

class ProviderModeRegistry:
    """
    Registry for provider-specific mode handlers.
    Example: Google image editing modes (edit-image-auto, edit-image-mask, etc.)
    """
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
    
    def register(self, mode_id: str, handler: Callable[[Any], Any]) -> None:
        """
        Register a mode handler.
        
        Args:
            mode_id: Mode identifier (e.g., 'edit-image-auto')
            handler: Handler function for this mode
        """
        self._handlers[mode_id] = handler
    
    def get(self, mode_id: str) -> Optional[Callable]:
        """
        Get mode handler.
        
        Args:
            mode_id: Mode identifier
        
        Returns:
            Handler function or None if not found
        """
        return self._handlers.get(mode_id)
    
    def list_modes(self) -> List[str]:
        """List all registered mode IDs."""
        return list(self._handlers.keys())
    
    def has_mode(self, mode_id: str) -> bool:
        """Check if mode is registered."""
        return mode_id in self._handlers
```

**Example: GoogleModeRegistry** (Backend Implementation):
```python
class GoogleModeRegistry(ProviderModeRegistry):
    """Google-specific mode registry for image editing operations."""
    
    def __init__(self):
        super().__init__()
        
        # Register Google-specific image editing modes
        self.register('image-outpainting', self._handle_outpainting)
        self.register('image-inpainting', self._handle_inpainting)
        self.register('virtual-try-on', self._handle_virtual_try_on)
        self.register('product-background-edit', self._handle_product_background)
    
    def _handle_outpainting(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle outpainting operation."""
        # Implementation for outpainting
        pass
    
    def _handle_inpainting(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle inpainting operation."""
        # Implementation for inpainting
        pass
    
    def _handle_virtual_try_on(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle virtual try-on operation."""
        # Implementation for virtual try-on
        pass
    
    def _handle_product_background(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle product background editing."""
        # Implementation for product background editing
        pass
```

### 4. Client Selection Strategy

**Purpose**: Determine which client (primary/secondary) to use for each operation.

**TypeScript Interface** (Conceptual):
```typescript
interface ClientSelector {
  /**
   * Select client based on operation requirements
   */
  select(
    operation: OperationType,
    capabilities: ProviderCapabilities,
    preferences: UserPreferences
  ): 'primary' | 'secondary';
}
```

**Python Class** (Backend Implementation):
```python
from typing import Dict, Any, Literal
from dataclasses import dataclass

@dataclass
class ProviderCapabilities:
    """Provider capability information."""
    streaming: bool
    function_call: bool
    vision: bool
    thinking: bool
    secondary_client_supported: bool

@dataclass
class UserPreferences:
    """User preferences for client selection."""
    preferred_client: Optional[Literal['primary', 'secondary']] = None

class ClientSelector:
    """Strategy for selecting between primary and secondary clients."""
    
    def select(
        self,
        operation: Dict[str, Any],
        capabilities: ProviderCapabilities,
        preferences: UserPreferences
    ) -> Literal['primary', 'secondary']:
        """
        Select client based on operation requirements.
        
        Args:
            operation: Operation details (type, parameters, required features)
            capabilities: Provider capabilities
            preferences: User preferences
        
        Returns:
            'primary' or 'secondary'
        """
        # Priority 1: User preference
        if preferences.preferred_client:
            return preferences.preferred_client
        
        # Priority 2: Operation requirements
        if operation.get('requires_advanced_features'):
            return 'primary'
        
        # Priority 3: Capability check
        if not capabilities.secondary_client_supported:
            return 'primary'
        
        # Priority 4: Performance optimization
        if operation.get('type') == 'chat' and capabilities.secondary_client_supported:
            return 'secondary'  # OpenAI-compatible is often faster for basic chat
        
        # Default: Primary client
        return 'primary'
```

### 5. Provider Configuration Schema

**Purpose**: Declarative configuration for all providers.

**TypeScript Schema** (Frontend API Contract):
```typescript
interface ProviderConfig {
  // Basic Info
  providerId: string;                    // e.g., 'google', 'qwen', 'ollama'
  name: string;                          // Display name
  description: string;                   // Description
  icon: string;                          // Icon identifier
  isCustom: boolean;                     // Is custom provider
  
  // Client Configuration
  clientType: 'google' | 'openai' | 'dashscope' | 'ollama';
  baseUrl: string;                       // Primary API endpoint
  defaultModel: string;                  // Default model
  
  // Dual-Client Support (Optional)
  secondaryClientType?: 'openai';        // Secondary client type
  secondaryBaseUrl?: string;             // Secondary API endpoint
  
  // Capabilities
  capabilities: {
    streaming: boolean;
    functionCall: boolean;
    vision: boolean;
    thinking: boolean;
    codeExecution: boolean;
  };
}
```

**Python Configuration** (Backend Implementation):
```python
from typing import Dict, Any, Optional, TypedDict

class ProviderConfigDict(TypedDict, total=False):
    """Provider configuration dictionary structure."""
    # Basic Info
    base_url: str
    default_model: str
    client_type: str  # 'google', 'openai', 'dashscope', 'ollama'
    name: str
    description: str
    icon: str
    is_custom: bool
    
    # Capabilities
    supports_streaming: bool
    supports_function_call: bool
    supports_vision: bool
    supports_thinking: bool
    
    # Dual-Client Support (Optional)
    secondary_client_type: Optional[str]
    secondary_base_url: Optional[str]

class ProviderConfig:
    """
    Provider configuration management.
    Configuration-driven design: All providers defined in Python dict.
    """
    
    # Provider configuration dictionary
    CONFIGS: Dict[str, ProviderConfigDict] = {
        "google": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "default_model": "gemini-2.0-flash-exp",
            "client_type": "google",
            "supports_streaming": True,
            "supports_function_call": True,
            "name": "Google Gemini",
            "description": "Native Google SDK. Supports Vision, Search & Thinking.",
            "icon": "gemini",
            "is_custom": False,
        },
        "tongyi": {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "default_model": "qwen-max",
            "client_type": "dashscope",
            "supports_streaming": True,
            "supports_function_call": True,
            "name": "Aliyun TongYi",
            "description": "Qwen models via DashScope.",
            "icon": "qwen",
            "is_custom": False,
            # Dual-client support
            "secondary_client_type": "openai",
            "secondary_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        },
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "default_model": "llama3",
            "client_type": "ollama",
            "supports_streaming": True,
            "supports_function_call": False,
            "name": "Ollama",
            "description": "Local models. Ensure CORS is enabled.",
            "icon": "ollama",
            "is_custom": False,
            # Dual-API support
            "secondary_base_url": "http://localhost:11434",  # Native API
        },
    }
    
    @classmethod
    def get_config(cls, provider: str) -> ProviderConfigDict:
        """Get provider configuration."""
        return cls.CONFIGS.get(provider, {})
    
    @classmethod
    def get_base_url(cls, provider: str) -> Optional[str]:
        """Get base URL for provider."""
        return cls.CONFIGS.get(provider, {}).get("base_url")
    
    @classmethod
    def get_client_type(cls, provider: str) -> Optional[str]:
        """Get client type for provider."""
        return cls.CONFIGS.get(provider, {}).get("client_type")
```

**Why Python Dict Instead of YAML/JSON**:
1. **Type Safety**: Python dicts with TypedDict provide IDE autocomplete and type checking
2. **No Parsing**: Direct access without file I/O or parsing overhead
3. **Code Colocation**: Configuration lives with code, easier to maintain
4. **Dynamic Values**: Can use Python expressions for computed values
5. **Import Safety**: Configuration errors caught at import time, not runtime
    webSearch: boolean;
  };
  
  // Provider-Specific Modes (Optional)
  modes?: string[];                      // e.g., ['image-outpainting', 'virtual-try-on']
  
  // Platform Routing (Google-specific)
  platformRouting?: {
    vertex: boolean;                     // Supports Vertex AI
    developer: boolean;                  // Supports Developer API
    defaultPlatform: 'vertex' | 'developer';
  };
}
```

**Example Configuration**:
```yaml
# provider-config.yaml

providers:
  google:
    providerId: google
    name: Google Gemini
    description: Native Google SDK. Supports Vision, Search & Thinking.
    icon: gemini
    isCustom: false
    clientType: google
    baseUrl: https://generativelanguage.googleapis.com/v1beta
    defaultModel: gemini-2.0-flash-exp
    capabilities:
      streaming: true
      functionCall: true
      vision: true
      thinking: true
      codeExecution: true
      webSearch: true
    modes:
      - image-outpainting
      - image-inpainting
      - virtual-try-on
      - product-background-edit
    platformRouting:
      vertex: true
      developer: true
      defaultPlatform: developer
  
  qwen:
    providerId: qwen
    name: Aliyun TongYi
    description: Qwen models with web search & code interpreter.
    icon: qwen
    isCustom: false
    clientType: dashscope
    baseUrl: https://dashscope.aliyuncs.com
    defaultModel: qwen-max
    secondaryClientType: openai
    secondaryBaseUrl: https://dashscope.aliyuncs.com/compatible-mode/v1
    capabilities:
      streaming: true
      functionCall: true
      vision: true
      thinking: true
      codeExecution: true
      webSearch: true
  
  ollama:
    providerId: ollama
    name: Ollama
    description: Local models with dynamic capability detection.
    icon: ollama
    isCustom: false
    clientType: openai
    baseUrl: http://localhost:11434
    defaultModel: llama3.2
    secondaryClientType: ollama-native
    secondaryBaseUrl: http://localhost:11434
    capabilities:
      streaming: true
      functionCall: true  # Detected dynamically
      vision: true        # Detected dynamically
      thinking: true      # Detected dynamically
      codeExecution: false
      webSearch: false
```

### 6. Provider Capability Detection

**Purpose**: Automatically detect provider capabilities from configuration or API.

**Interface**:
```typescript
interface CapabilityDetector {
  /**
   * Detect provider capabilities
   */
  detect(providerId: string, client: ProviderClient): Promise<ProviderCapabilities>;
  
  /**
   * Get cached capabilities
   */
  getCached(providerId: string): ProviderCapabilities | null;
}
```

**Implementation** (from Ollama backend):
```typescript
class OllamaCapabilityDetector implements CapabilityDetector {
  private cache: Map<string, ProviderCapabilities> = new Map();
  private cacheTTL = 3600000; // 1 hour
  
  async detect(providerId: string, client: OllamaClient): Promise<ProviderCapabilities> {
    // Check cache
    const cached = this.getCached(providerId);
    if (cached) return cached;
    
    // Call /api/show to get model capabilities
    const modelInfo = await client.native.get(`/api/show`, {
      params: { name: client.defaultModel }
    });
    
    const capabilities: ProviderCapabilities = {
      streaming: true,
      functionCall: modelInfo.capabilities?.includes('tools') || false,
      vision: modelInfo.capabilities?.includes('vision') || false,
      thinking: modelInfo.capabilities?.includes('thinking') || false,
      contextLength: modelInfo.context_length || 4096,
    };
    
    // Cache result
    this.cache.set(providerId, capabilities);
    setTimeout(() => this.cache.delete(providerId), this.cacheTTL);
    
    return capabilities;
  }
  
  getCached(providerId: string): ProviderCapabilities | null {
    return this.cache.get(providerId) || null;
  }
}
```

## Frontend Integration Components

These components remain in the frontend and are responsible for UI orchestration and backend API access.

1. **Provider Templates Client**: Fetches provider metadata from `/api/providers/templates` (SSOT).
2. **UnifiedProviderClient / LLMFactory**: Routes all provider operations to backend endpoints.
3. **StrategyRegistry / Handlers**: Maps UI modes to backend operations; provider-specific mode logic stays on the backend.

### Tongyi Mixed-Mode Note

Tongyi remains mixed-mode for now:
- Chat/models are handled by backend routes (`/api/chat/tongyi`, `/api/models/tongyi`).
- Image generation keeps the existing frontend DashScope proxy flow until a later unification pass.

## Correctness Properties

### Registry Properties

1. **Round-trip**: `registry.get(registry.register(id, handler)) === handler`
2. **Uniqueness**: Registering same ID twice overwrites previous handler
3. **Null safety**: `registry.get(unknownId) === null`

### Factory Properties

4. **Determinism**: Same inputs → same client instance (cached)
5. **Validation**: Invalid providerId throws descriptive error
6. **Auto-registration**: Factory auto-registers on first use

### Dual-Client Properties

7. **Primary fallback**: If secondary unavailable, use primary
8. **Client selection**: Selection is deterministic based on operation type
9. **Error handling**: Client errors trigger fallback to secondary (if available)

### Configuration Properties

10. **Schema validation**: Invalid config throws validation errors at startup
11. **Required fields**: providerId, clientType, baseUrl, defaultModel are required
12. **Optional fields**: secondaryClientType, modes, platformRouting are optional

### Capability Detection Properties

13. **Cache hit**: Cached capabilities returned without API call
14. **Cache miss**: API call made and result cached
15. **TTL expiry**: Cached capabilities expire after TTL

### Performance Properties

16. **Client caching**: Clients cached per (providerId, apiKey) pair
17. **Lazy initialization**: Clients created only when needed
18. **Memory efficiency**: Cache size limited, old entries evicted

## Migration Guide

### Phase 1: Backend (Already Complete)

✅ Backend already implements unified provider architecture:
- `ProviderConfig.CONFIGS` defines all providers
- `ProviderFactory` auto-registers based on `client_type`
- Qwen and Ollama implement dual-client patterns

### Phase 2: Frontend Integration (To Be Implemented)

**Step 1**: Consume provider templates from backend SSOT
- Use `/api/providers/templates` as the only provider configuration source
- Avoid frontend static provider config files

**Step 2**: Route provider operations through the backend
- Ensure `LLMFactory`/`UnifiedProviderClient` are the default path for SSOT-managed providers
- Do not instantiate provider SDKs in the frontend

**Step 3**: Keep the handler system as the UI orchestration layer
- StrategyRegistry remains the mode entry point
- Provider-specific mode logic stays in backend services

**Step 4**: Document exceptions and defer unification
- Tongyi stays mixed-mode (backend chat/models, frontend image proxy)
- Schedule future unification as a separate phase

## Testing Strategy

Note: ProviderClientFactory, dual-client selection, and capability detection are backend-owned. Frontend testing focuses on template loading and API routing.

### Unit Tests

1. **ProviderClientFactory**:
   - Test auto-registration
   - Test client caching
   - Test error handling for unknown providers

2. **Dual-Client Providers**:
   - Test client selection logic
   - Test fallback behavior
   - Test error handling

3. **Mode Registries**:
   - Test handler registration
   - Test handler lookup
   - Test mode listing

4. **Capability Detection**:
   - Test cache hit/miss
   - Test TTL expiry
   - Test API error handling

### Integration Tests

1. **End-to-End Provider Tests**:
   - Test Google provider with Vertex AI and Developer API
   - Test Qwen provider with DashScope and OpenAI-compatible API
   - Test Ollama provider with OpenAI-compatible and native API

2. **Migration Tests**:
   - Test backward compatibility with existing handlers
   - Test gradual migration (some providers migrated, some not)

### Property-Based Tests

1. **Registry Properties**: Test round-trip, uniqueness, null safety
2. **Factory Properties**: Test determinism, validation, auto-registration
3. **Dual-Client Properties**: Test fallback, selection, error handling

## Documentation

### Developer Documentation

1. **Provider Configuration Guide**: How to add new providers
2. **Dual-Client Guide**: How to implement dual-client support
3. **Mode Registry Guide**: How to add provider-specific modes
4. **Migration Guide**: How to migrate existing providers

### API Documentation

1. **ProviderClientFactory API**: TypeScript interfaces and examples
2. **DualClientProvider API**: Client selection and execution
3. **ProviderModeRegistry API**: Mode registration and lookup
4. **CapabilityDetector API**: Capability detection and caching

## References

- Backend implementation: `backend/app/services/provider_factory.py`
- Qwen dual-client: `backend/app/services/qwen_native.py`
- Ollama dual-API: `backend/app/services/ollama/ollama.py`
- Provider configuration: `backend/app/services/provider_config.py`
