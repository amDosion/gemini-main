# Unified Provider Client Architecture - Implementation Tasks

## Overview

This document outlines the implementation tasks for the **unified provider client architecture** where **backend is the single source of truth (SSOT)** for provider configuration, client creation, and routing. The frontend is a thin API client that consumes backend templates and routes requests through backend APIs.

**Key Principle**: Backend owns provider logic; frontend orchestrates UI and calls backend APIs.

## Task Breakdown

### Phase 1: Backend Foundation (Core Infrastructure)

#### Task 1.0: Add Python Interface Definitions to Design Document

**Priority**: P0 (Blocking)  
**Estimated Effort**: 2 hours  
**Dependencies**: None  
**Owner**: Documentation  
**Status**: ✅ COMPLETED

**Description**: Add Python interface definitions alongside existing TypeScript interfaces in design.md to address language inconsistency between design (TypeScript) and implementation (Python).

**Acceptance Criteria**:
- [x] Add Python type hints for all core interfaces in design.md:
  - [x] `ProviderClientFactory` (Python version)
  - [x] `DualClientProvider` (Python version)
  - [x] `ProviderModeRegistry` (Python version)
  - [x] `ClientSelector` (Python version)
  - [x] `ProviderConfig` (Python version using TypedDict)
- [x] Keep existing TypeScript interfaces for frontend reference
- [x] Add note explaining: "TypeScript interfaces are for frontend type definitions; Python interfaces show actual backend implementation"
- [x] Ensure Python interfaces match actual implementation signatures in `provider_factory.py`, `qwen_native.py`, `ollama.py`
- [x] Add Python examples for Qwen and Ollama dual-client implementations
- [x] Add Python dict configuration rationale

**Files Modified**:
- `.kiro/specs/unified-provider-architecture/design.md`

**Completion Notes**:
- Added Python class definitions for all 5 core interfaces
- Included complete Python examples from actual backend implementation
- Added explanatory note about TypeScript (frontend) vs Python (backend)
- Documented Python dict configuration advantages over YAML/JSON
- All Python signatures match actual backend implementation
from typing import Optional, Dict, Type
from .base_provider import BaseProviderService

class ProviderFactory:
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
        """Create a provider service instance."""
        pass
    
    @classmethod
    def register(cls, provider: str, service_class: Type[BaseProviderService]) -> None:
        """Register a provider service class."""
        pass
    
    @classmethod
    def get_cached(cls, provider: str, api_key: str) -> Optional[BaseProviderService]:
        """Get cached client instance."""
        pass
```
```

**Validates**: Requirements 10 (Documentation)

**Addresses Analysis Issues**:
- ✅ Issue #1 (High): Resolves language inconsistency by providing both TypeScript and Python interfaces

---

#### Task 1.1: Create Unified Provider Configuration (Backend SSOT)

**Priority**: P0 (Blocking)  
**Estimated Effort**: 3 hours  
**Dependencies**: None  
**Owner**: Backend  
**Status**: ✅ COMPLETED

**Description**: Create a centralized Python configuration in backend defining all providers with their capabilities, client types, and endpoints. **Note**: Current implementation uses Python dict in `provider_config.py` instead of YAML/JSON for better type safety and IDE support.

**Acceptance Criteria**:
- [x] Enhance existing `backend/app/services/provider_config.py` with complete provider definitions
- [x] Define schema with fields: providerId, clientType, baseUrl, defaultModel, capabilities
- [x] Add configuration for all existing providers (Google, OpenAI, DeepSeek, Qwen, Ollama, etc.)
- [x] Include dual-client configuration for Qwen and Ollama (mark as optional feature)
- [x] Add Google-specific modes and platform routing config
- [x] Validate configuration schema at backend startup
- [x] Ensure `/api/providers/templates` endpoint exposes config to frontend (already exists)

**Files Modified**:
- `backend/app/services/provider_config.py` (enhanced existing CONFIGS dict)

**Implementation Notes**: 
- Current implementation uses Python dict instead of YAML/JSON
- Rationale: Better type safety, IDE autocomplete, no file I/O overhead
- Dual-client support is OPTIONAL - only Qwen and Ollama implement it currently

**Completion Notes**:
- Added capability fields to all providers: `supports_vision`, `supports_thinking`, `supports_web_search`, `supports_code_execution`
- Added dual-client configuration for Tongyi/Qwen: `secondary_client_type`, `secondary_base_url`
- Added dual-API configuration for Ollama: `secondary_base_url` (native API endpoint)
- Changed Ollama `client_type` from "openai" to "ollama" for dedicated service
- Added Google-specific configuration: `modes` list and `platform_routing` dict
- Added utility methods: `supports_vision()`, `supports_thinking()`, `supports_web_search()`, `supports_code_execution()`, `get_secondary_client_type()`, `get_secondary_base_url()`, `has_dual_client_support()`, `get_modes()`, `get_platform_routing()`
- Enhanced `validate_config()` to check dual-client configuration consistency
- Enhanced `validate_all_configs()` to log dual-client providers
- Enhanced `get_provider_templates()` to include capabilities, dualClient, modes, platformRouting in response

**Example Config** (Python dict format):
```python
CONFIGS: Dict[str, Dict[str, Any]] = {
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
        # Optional: dual-client support (not implemented for Google yet)
        # "secondary_client_type": "openai",
        # "secondary_base_url": "...",
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
        # Dual-client support (already implemented in QwenNativeProvider)
        "secondary_client_type": "openai",
        "secondary_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    }
}
```

**Validates**: Requirements 5, 12, 18

**Addresses Analysis Issues**:
- ✅ Issue #4 (Medium): Documents why Python dict is used instead of YAML/JSON
- ✅ Issue #2 (High): Clarifies dual-client is optional, not universal

---

#### Task 1.2: Enhance ProviderClientFactory (Backend)

**Priority**: P0 (Blocking)  
**Estimated Effort**: 4 hours  
**Dependencies**: Task 1.1  
**Owner**: Backend

**Description**: Enhance existing `ProviderFactory` to support optional dual-client mode and add client instance caching. **Note**: Dual-client is only for Qwen/Ollama initially.

**Acceptance Criteria**:
- [ ] Load provider config from `ProviderConfig.CONFIGS` at startup (already implemented)
- [ ] Support optional dual-client creation (primary + secondary) for providers that define `secondary_client_type`
- [ ] Implement client selection strategy based on operation type (only for dual-client providers)
- [ ] **Add client instance caching** per (providerId, apiKey, clientType) tuple (currently missing)
- [ ] Add error handling for unknown providers (already implemented)
- [ ] Add logging for factory operations (already implemented)
- [ ] Validate credentials before creating clients

**Files to Modify**:
- `backend/app/services/provider_factory.py` (add caching mechanism)
- `backend/app/services/provider_config.py` (add optional secondary_client_type fields)

**Reference**: Existing `ProviderFactory` already implements auto-registration based on `client_type`

**Implementation Note**:
- Current implementation: `ProviderFactory.create()` creates new instance every time
- Required: Add `_client_cache: Dict[str, BaseProviderService]` to cache instances
- Cache key format: `f"{provider}:{api_key}:{client_type}"`
- Add `getCached()` method to retrieve cached instances

**Python Interface** (add to design.md):
```python
class ProviderFactory:
    _client_cache: Dict[str, BaseProviderService] = {}
    
    @classmethod
    def create(cls, provider: str, api_key: str, ...) -> BaseProviderService:
        cache_key = f"{provider}:{api_key}"
        if cache_key in cls._client_cache:
            return cls._client_cache[cache_key]
        
        # Create new instance
        service = cls._create_instance(provider, api_key, ...)
        cls._client_cache[cache_key] = service
        return service
    
    @classmethod
    def get_cached(cls, provider: str, api_key: str) -> Optional[BaseProviderService]:
        cache_key = f"{provider}:{api_key}"
        return cls._client_cache.get(cache_key)
```

**Validates**: Requirements 11, 12, 13

**Addresses Analysis Issues**:
- ✅ Issue #3 (High): Adds missing client caching mechanism
- ✅ Issue #1 (High): Adds Python interface definition alongside TypeScript

---

#### Task 1.3: Implement Client Selection Strategy (Backend)

**Priority**: P0 (Blocking)  
**Estimated Effort**: 3 hours  
**Dependencies**: Task 1.2  
**Owner**: Backend

**Description**: Implement logic to select between primary and secondary clients based on operation type and capabilities.

**Acceptance Criteria**:
- [ ] Create `backend/app/services/client_selector.py`
- [ ] Define `ClientSelector` interface
- [ ] Implement `DefaultClientSelector` with priority logic:
  1. User preference
  2. Operation requirements (advanced features → primary)
  3. Capability check (secondary not available → primary)
  4. Performance optimization (basic chat → secondary if available)
- [ ] Support custom selection strategies per provider
- [ ] Add fallback to primary client on error
- [ ] Add logging for client selection decisions

**Files to Create**:
- `backend/app/services/client_selector.py`

**Validates**: Requirements 13, 15

---

### Phase 2: Google Provider Migration (Backend)

#### Task 2.1: Create GoogleModeRegistry (Backend)

**Priority**: P1 (High)  
**Estimated Effort**: 5 hours  
**Dependencies**: Task 1.1  
**Owner**: Backend

**Description**: Create a registry for Google-specific modes (outpainting, inpainting, try-on, etc.) in backend.

**Acceptance Criteria**:
- [ ] Create `backend/app/services/gemini/mode_registry.py`
- [ ] Define `ModeHandler` interface
- [ ] Implement `GoogleModeRegistry` class with `register()` and `get()` methods
- [ ] Register existing Google modes:
  - [ ] image-outpainting
  - [ ] image-inpainting
  - [ ] virtual-try-on
  - [ ] product-background-edit (future)
- [ ] Add mode validation
- [ ] Add mode listing
- [ ] Load mode configuration from `providers.yaml`

**Files to Create**:
- `backend/app/services/gemini/mode_registry.py`
- `backend/app/services/gemini/handlers/outpainting_handler.py`
- `backend/app/services/gemini/handlers/inpainting_handler.py`
- `backend/app/services/gemini/handlers/virtual_tryon_handler.py`

**Validates**: Requirements 1, 14

---

#### Task 2.2: Enhance GoogleClientFactory (Backend)

**Priority**: P1 (High)  
**Estimated Effort**: 4 hours  
**Dependencies**: Task 2.1  
**Owner**: Backend

**Description**: Enhance existing Google service to support dual-client mode (Vertex AI + Developer API).

**Acceptance Criteria**:
- [ ] Modify `backend/app/services/gemini/google_service.py`
- [ ] Support creating both Vertex AI and Developer API clients
- [ ] Implement client caching to avoid redundant initialization
- [ ] Validate required credentials before creating clients
- [ ] Add error handling for missing credentials
- [ ] Add logging for client creation

**Files to Modify**:
- `backend/app/services/gemini/google_service.py`

**Reference**: Existing `GoogleService` already supports Vertex AI and Developer API

**Validates**: Requirements 2, 13

---

#### Task 2.3: Implement Google Platform Routing (Backend)

**Priority**: P1 (High)  
**Estimated Effort**: 3 hours  
**Dependencies**: Task 2.2  
**Owner**: Backend

**Description**: Implement logic to route between Vertex AI and Developer API based on mode and user preference.

**Acceptance Criteria**:
- [ ] Create `backend/app/services/gemini/platform_routing.py`
- [ ] Implement `resolvePlatform()` function
- [ ] Support mode-based routing (some modes only on Vertex AI)
- [ ] Support user preference override
- [ ] Add deterministic routing logic
- [ ] Load platform support from `providers.yaml`
- [ ] Add logging for routing decisions

**Files to Create**:
- `backend/app/services/gemini/platform_routing.py`

**Reference**: `.kiro/specs/参考/image_backend/image_backend/app/core/routing.py`

**Validates**: Requirements 3

---

#### Task 2.4: Create Google Mode API Endpoints (Backend)

**Priority**: P1 (High)  
**Estimated Effort**: 4 hours  
**Dependencies**: Task 2.1, Task 2.3  
**Owner**: Backend

**Description**: Create backend API endpoints for Google-specific modes that frontend will call.

**Acceptance Criteria**:
- [ ] Create `/api/google/modes` endpoint (list available modes)
- [ ] Create `/api/google/outpaint` endpoint
- [ ] Create `/api/google/inpaint` endpoint
- [ ] Create `/api/google/virtual-tryon` endpoint
- [ ] Add request validation
- [ ] Add error handling
- [ ] Add logging with request IDs
- [ ] Document API endpoints

**Files to Create**:
- `backend/app/api/routes/google_modes.py`

**Validates**: Requirements 1, 4, 7

---

#### Task 2.5: Document Backend API Endpoints

**Priority**: P1 (High)  
**Estimated Effort**: 2 hours  
**Dependencies**: Task 2.4  
**Owner**: Documentation

**Description**: Create comprehensive API endpoint documentation listing all backend endpoints that frontend will consume.

**Acceptance Criteria**:
- [ ] Add "Backend API Endpoints" section to design.md
- [ ] Document all provider-related endpoints:
  - [ ] `GET /api/providers/templates` - Get provider configuration templates
  - [ ] `GET /api/models/{provider}` - Get available models for provider
  - [ ] `POST /api/chat/{provider}` - Chat with provider
  - [ ] `POST /api/google/outpaint` - Google outpainting
  - [ ] `POST /api/google/inpaint` - Google inpainting
  - [ ] `POST /api/google/virtual-tryon` - Google virtual try-on
  - [ ] `GET /api/google/modes` - List Google modes
- [ ] Include request/response schemas for each endpoint
- [ ] Add authentication requirements
- [ ] Add error response formats

**Files to Modify**:
- `.kiro/specs/unified-provider-architecture/design.md`

**Example Documentation**:
```markdown
## Backend API Endpoints

### Provider Configuration

#### GET /api/providers/templates
Get all provider configuration templates (SSOT).

**Response**:
```json
[
  {
    "id": "google",
    "name": "Google Gemini",
    "protocol": "google",
    "baseUrl": "https://...",
    "defaultModel": "gemini-2.0-flash-exp",
    "description": "...",
    "isCustom": false,
    "icon": "gemini"
  }
]
```

### Google-Specific Modes

#### POST /api/google/outpaint
Perform image outpainting using Google Imagen.

**Request**:
```json
{
  "image": "base64_or_url",
  "prompt": "extend the image...",
  "model": "imagen-3.0-generate-001"
}
```

**Response**:
```json
{
  "images": ["base64_result"],
  "usage": {...}
}
```
```

**Validates**: Requirements 10 (Documentation)

**Addresses Analysis Issues**:
- ✅ Issue #5 (Medium): Adds missing API endpoint documentation

---

### Phase 3: Frontend Integration (Thin Client)

#### Task 3.1: Create Frontend Provider Template Loader

**Priority**: P1 (High)  
**Estimated Effort**: 3 hours  
**Dependencies**: Task 1.1  
**Owner**: Frontend

**Description**: Create frontend service to load provider templates from backend SSOT (`/api/providers/templates`).

**Acceptance Criteria**:
- [ ] Create `frontend/services/ProviderTemplateLoader.ts`
- [ ] Call `/api/providers/templates` to get provider config
- [ ] Cache templates in memory
- [ ] Define TypeScript interfaces matching backend schema
- [ ] Add error handling for API failures
- [ ] Add logging for template loading

**Files to Create**:
- `frontend/services/ProviderTemplateLoader.ts`
- `frontend/types/provider-types.ts`

**Validates**: Requirements 18

---

#### Task 3.2: Update Frontend Handler System to Route Through Backend

**Priority**: P1 (High)  
**Estimated Effort**: 5 hours  
**Dependencies**: Task 3.1, Task 2.4  
**Owner**: Frontend

**Description**: Update frontend handlers to route Google mode operations through backend APIs instead of direct SDK calls.

**Acceptance Criteria**:
- [ ] Modify Google handlers to call backend APIs:
  - [ ] Outpainting → `/api/google/outpaint`
  - [ ] Inpainting → `/api/google/inpaint`
  - [ ] Virtual Try-On → `/api/google/virtual-tryon`
- [ ] Keep existing Handler interface unchanged
- [ ] Maintain backward compatibility with non-Google providers
- [ ] Add error handling for API failures
- [ ] Add logging for handler operations

**Files to Modify**:
- `frontend/hooks/handlers/AllHandlerClasses.ts`
- `frontend/hooks/handlers/strategyConfig.ts`

**Validates**: Requirements 6

---

#### Task 3.3: Remove Frontend Provider SDK Dependencies (Google Only)

**Priority**: P2 (Medium)  
**Estimated Effort**: 2 hours  
**Dependencies**: Task 3.2  
**Owner**: Frontend

**Description**: Remove direct Google GenAI SDK imports from frontend since all Google operations now route through backend.

**Acceptance Criteria**:
- [ ] Remove `@google/generative-ai` imports from Google handlers
- [ ] Remove Google SDK initialization code
- [ ] Keep SDK for other providers (OpenAI, DeepSeek, etc.) unchanged
- [ ] Update package.json if SDK is no longer needed
- [ ] Verify all Google operations work through backend APIs

**Files to Modify**:
- `frontend/hooks/handlers/AllHandlerClasses.ts`
- `package.json` (if removing SDK)

**Validates**: Requirements 6

---

### Phase 4: Qwen Provider Migration (Backend)

#### Task 4.1: Enhance QwenDualClientProvider (Backend)

**Priority**: P2 (Medium)  
**Estimated Effort**: 4 hours  
**Dependencies**: Task 1.3  
**Owner**: Backend

**Description**: Enhance existing Qwen provider to use new client selection strategy.

**Acceptance Criteria**:
- [ ] Modify `backend/app/services/qwen_native.py`
- [ ] Integrate with `ClientSelector` for operation-based client selection
- [ ] Ensure primary client (DashScope native SDK) is used for:
  - [ ] Web search (`enable_search`)
  - [ ] Code interpreter plugin
  - [ ] PDF parsing plugin
  - [ ] Thinking models
- [ ] Ensure secondary client (OpenAI-compatible) is used for basic chat
- [ ] Add error handling and fallback
- [ ] Add logging for client selection

**Files to Modify**:
- `backend/app/services/qwen_native.py`

**Reference**: Existing `QwenNativeProvider` already implements dual-client pattern

**Validates**: Requirements 13, 15

---

#### Task 4.2: Create Qwen Mode API Endpoints (Backend)

**Priority**: P3 (Low)  
**Estimated Effort**: 3 hours  
**Dependencies**: Task 4.1  
**Owner**: Backend

**Description**: Create backend API endpoints for Qwen-specific advanced features.

**Acceptance Criteria**:
- [ ] Create `/api/qwen/search` endpoint (web search)
- [ ] Create `/api/qwen/code-interpreter` endpoint
- [ ] Create `/api/qwen/pdf-parser` endpoint
- [ ] Add request validation
- [ ] Add error handling
- [ ] Add logging with request IDs

**Files to Create**:
- `backend/app/api/routes/qwen_modes.py`

**Validates**: Requirements 14

---

### Phase 5: Ollama Provider Migration (Backend)

#### Task 5.1: Enhance OllamaDualClientProvider (Backend)

**Priority**: P2 (Medium)  
**Estimated Effort**: 4 hours  
**Dependencies**: Task 1.3  
**Owner**: Backend

**Description**: Enhance existing Ollama provider to use new client selection strategy.

**Acceptance Criteria**:
- [ ] Modify `backend/app/services/ollama/ollama.py`
- [ ] Integrate with `ClientSelector` for operation-based client selection
- [ ] Ensure primary client (OpenAI-compatible API `/v1/*`) is used for chat
- [ ] Ensure secondary client (native Ollama API `/api/*`) is used for:
  - [ ] Model management
  - [ ] Embedding
  - [ ] Capability detection
- [ ] Add error handling and fallback
- [ ] Add logging for client selection

**Files to Modify**:
- `backend/app/services/ollama/ollama.py`

**Reference**: Existing `OllamaService` already implements dual-API pattern

**Validates**: Requirements 13, 15

---

#### Task 5.2: Implement Ollama Capability Detection (Backend)

**Priority**: P2 (Medium)  
**Estimated Effort**: 3 hours  
**Dependencies**: Task 5.1  
**Owner**: Backend

**Description**: Enhance existing Ollama capability detection to use new caching strategy.

**Acceptance Criteria**:
- [ ] Modify `backend/app/services/ollama/ollama.py`
- [ ] Call `/api/show` to get model capabilities
- [ ] Detect: tools, vision, thinking, context_length
- [ ] Implement TTL caching (1 hour) using shared cache
- [ ] Add error handling for API failures
- [ ] Add logging for capability detection

**Files to Modify**:
- `backend/app/services/ollama/ollama.py`

**Reference**: Existing `OllamaService` already implements capability detection with TTLCache

**Validates**: Requirements 16

---

### Phase 6: Error Handling and Logging (Backend)

#### Task 6.1: Implement Unified Error Handling (Backend)

**Priority**: P1 (High)  
**Estimated Effort**: 4 hours  
**Dependencies**: Task 1.2  
**Owner**: Backend

**Description**: Create unified error handling system for all providers.

**Acceptance Criteria**:
- [ ] Create `backend/app/services/errors.py`
- [ ] Define `ProviderError` base class with context fields:
  - [ ] providerId
  - [ ] clientType
  - [ ] operation
  - [ ] context (dict)
- [ ] Define specific error classes:
  - [ ] `ClientCreationError`
  - [ ] `OperationError`
  - [ ] `ConfigurationError`
- [ ] Add error recovery strategies (retry, fallback)
- [ ] Add structured logging with request IDs
- [ ] Update all providers to use new error classes

**Files to Create**:
- `backend/app/services/errors.py`

**Files to Modify**:
- `backend/app/services/provider_factory.py`
- `backend/app/services/gemini/google_service.py`
- `backend/app/services/qwen_native.py`
- `backend/app/services/ollama/ollama.py`

**Validates**: Requirements 7, 17

---

#### Task 6.2: Implement Structured Logging (Backend)

**Priority**: P1 (High)  
**Estimated Effort**: 3 hours  
**Dependencies**: Task 6.1  
**Owner**: Backend

**Description**: Implement structured logging across all provider operations.

**Acceptance Criteria**:
- [ ] Add request ID generation and propagation
- [ ] Log all provider operations with context:
  - [ ] providerId
  - [ ] operation type
  - [ ] client type (primary/secondary)
  - [ ] platform (for Google)
  - [ ] execution time
- [ ] Use consistent log levels (DEBUG, INFO, WARNING, ERROR)
- [ ] Add log aggregation support (JSON format)

**Files to Modify**:
- `backend/app/services/provider_factory.py`
- `backend/app/services/client_selector.py`
- `backend/app/services/gemini/google_service.py`
- `backend/app/services/gemini/platform_routing.py`

**Validates**: Requirements 7

---

### Phase 7: Testing and Documentation

#### Task 7.1: Create Backend Unit Tests

**Priority**: P1 (High)  
**Estimated Effort**: 8 hours  
**Dependencies**: All backend implementation tasks  
**Owner**: Backend

**Description**: Create comprehensive unit tests for all new backend components.

**Test Coverage**:
- [ ] ProviderClientFactory tests:
  - [ ] Auto-registration from config
  - [ ] Client caching
  - [ ] Dual-client creation
  - [ ] Error handling
- [ ] ClientSelector tests:
  - [ ] Selection logic
  - [ ] Fallback behavior
  - [ ] Custom strategies
- [ ] GoogleModeRegistry tests:
  - [ ] Handler registration
  - [ ] Handler lookup
  - [ ] Mode listing
- [ ] Platform routing tests:
  - [ ] Deterministic routing
  - [ ] User preference override
  - [ ] Error handling
- [ ] Capability detection tests:
  - [ ] Cache hit/miss
  - [ ] TTL expiry
  - [ ] API error handling

**Files to Create**:
- `backend/tests/services/test_provider_factory.py`
- `backend/tests/services/test_client_selector.py`
- `backend/tests/services/gemini/test_mode_registry.py`
- `backend/tests/services/gemini/test_platform_routing.py`
- `backend/tests/services/ollama/test_capability_detection.py`

**Validates**: Requirements 9

---

#### Task 7.2: Create Backend Integration Tests

**Priority**: P2 (Medium)  
**Estimated Effort**: 6 hours  
**Dependencies**: Task 7.1  
**Owner**: Backend

**Description**: Create end-to-end integration tests for provider workflows.

**Test Coverage**:
- [ ] Google provider E2E:
  - [ ] Vertex AI chat
  - [ ] Developer API chat
  - [ ] Image outpainting
  - [ ] Image inpainting
  - [ ] Virtual try-on
- [ ] Qwen provider E2E:
  - [ ] Basic chat (OpenAI-compatible)
  - [ ] Web search (native SDK)
  - [ ] Code interpreter (native SDK)
- [ ] Ollama provider E2E:
  - [ ] Chat (OpenAI-compatible)
  - [ ] Model management (native API)
  - [ ] Capability detection

**Files to Create**:
- `backend/tests/integration/test_google_provider.py`
- `backend/tests/integration/test_qwen_provider.py`
- `backend/tests/integration/test_ollama_provider.py`

**Validates**: Requirements 9

---

#### Task 7.3: Create Property-Based Tests

**Priority**: P3 (Low)  
**Estimated Effort**: 4 hours  
**Dependencies**: Task 7.1  
**Owner**: Backend

**Description**: Create property-based tests for correctness properties.

**Test Coverage**:
- [ ] Registry properties:
  - [ ] **Property 1**: Round-trip (register → get → same handler)
  - [ ] **Property 2**: Uniqueness (duplicate ID overwrites)
  - [ ] **Property 3**: Null safety (unknown ID → null)
- [ ] Factory properties:
  - [ ] **Property 4**: Determinism (same inputs → same cached instance)
  - [ ] **Property 5**: Validation (invalid providerId → error)
  - [ ] **Property 6**: Auto-registration (first use → registered)
- [ ] Dual-client properties:
  - [ ] **Property 7**: Primary fallback (no secondary → primary)
  - [ ] **Property 8**: Selection determinism (same operation → same client)
  - [ ] **Property 9**: Error handling (client error → fallback)
- [ ] Configuration properties:
  - [ ] **Property 10**: Schema validation (invalid config → error)
  - [ ] **Property 11**: Required fields (missing required → error)
  - [ ] **Property 12**: Optional fields (missing optional → OK)
- [ ] Capability detection properties:
  - [ ] **Property 13**: Cache hit (cached → no API call)
  - [ ] **Property 14**: Cache miss (not cached → API call)
  - [ ] **Property 15**: TTL expiry (expired → new API call)
- [ ] Performance properties:
  - [ ] **Property 16**: Client caching (same key → same instance)
  - [ ] **Property 17**: Lazy initialization (not used → not created)
  - [ ] **Property 18**: Memory efficiency (cache size limited)

**Files to Create**:
- `backend/tests/properties/test_registry_properties.py`
- `backend/tests/properties/test_factory_properties.py`
- `backend/tests/properties/test_dual_client_properties.py`

**Validates**: Design correctness properties

---

#### Task 7.4: Create Developer Documentation

**Priority**: P1 (High)  
**Estimated Effort**: 6 hours  
**Dependencies**: All implementation tasks  
**Owner**: Backend + Frontend

**Description**: Create comprehensive developer documentation.

**Documentation to Create**:
- [ ] **Provider Configuration Guide**: How to add new providers to `providers.yaml`
- [ ] **Dual-Client Implementation Guide**: How to implement dual-client support
- [ ] **Mode Registry Guide**: How to add provider-specific modes
- [ ] **Migration Guide**: How to migrate existing providers
- [ ] **API Reference**: Backend API endpoints documentation
- [ ] **Frontend Integration Guide**: How frontend consumes backend APIs

**Files to Create**:
- `.kiro/docs/providers/provider-configuration-guide.md`
- `.kiro/docs/providers/dual-client-guide.md`
- `.kiro/docs/providers/mode-registry-guide.md`
- `.kiro/docs/providers/migration-guide.md`
- `.kiro/docs/providers/api-reference.md`
- `.kiro/docs/providers/frontend-integration-guide.md`

**Validates**: Requirements 10

---

#### Task 7.5: Update Steering Files

**Priority**: P2 (Medium)  
**Estimated Effort**: 2 hours  
**Dependencies**: Task 7.4  
**Owner**: Documentation

**Description**: Update steering files to reference new provider architecture.

**Files to Update**:
- `.kiro/powers/gemini-fullstack/steering/backend-development.md`
- `.kiro/powers/gemini-fullstack/steering/frontend-development.md`
- `.kiro/powers/gemini-fullstack/steering/gemini-integration.md`

**Validates**: Requirements 10

---

### Phase 8: Migration and Cleanup

#### Task 8.1: Migrate Remaining Providers (Backend)

**Priority**: P3 (Low)  
**Estimated Effort**: 8 hours  
**Dependencies**: Task 7.1  
**Owner**: Backend

**Description**: Migrate remaining providers (OpenAI, DeepSeek, Moonshot, etc.) to use ProviderClientFactory.

**Providers to Migrate**:
- [ ] OpenAI
- [ ] DeepSeek
- [ ] Moonshot
- [ ] Zhipu
- [ ] SiliconFlow
- [ ] Custom providers

**Note**: These providers don't need dual-client support, just factory integration.

**Validates**: Requirements 19

---

#### Task 8.2: Document Tongyi Exception (Mixed-Mode)

**Priority**: P2 (Medium)  
**Estimated Effort**: 1 hour  
**Dependencies**: None  
**Owner**: Documentation

**Description**: Document Tongyi's current mixed-mode behavior and future unification plan.

**Acceptance Criteria**:
- [ ] Document current state:
  - [ ] Backend: Chat/models via `/api/chat/tongyi`, `/api/models/tongyi`
  - [ ] Frontend: Image generation via existing DashScope proxy flow
- [ ] Document rationale for keeping mixed-mode
- [ ] Create future unification plan as separate phase

**Files to Create**:
- `.kiro/docs/providers/tongyi-mixed-mode.md`

**Validates**: Requirements 21

---

## Task Dependencies Graph

```
Phase 1: Backend Foundation
  Task 1.1 (Provider Config YAML)
    ↓
  Task 1.2 (ProviderClientFactory)
    ↓
  Task 1.3 (ClientSelector)
    ↓
  ┌─────────────┬─────────────┬─────────────┐
  ↓             ↓             ↓             ↓
Phase 2       Phase 4       Phase 5       Phase 6
Google        Qwen          Ollama        Errors
  ↓             ↓             ↓             ↓
Task 2.1      Task 4.1      Task 5.1      Task 6.1
  ↓             ↓             ↓             ↓
Task 2.2      Task 4.2      Task 5.2      Task 6.2
  ↓
Task 2.3
  ↓
Task 2.4
  ↓
  └─────────────┴─────────────┴─────────────┘
              ↓
        Phase 3: Frontend
          Task 3.1 (Template Loader)
            ↓
          Task 3.2 (Update Handlers)
            ↓
          Task 3.3 (Remove SDK)
            ↓
        Phase 7: Testing & Docs
          Task 7.1 (Unit Tests)
            ↓
          Task 7.2 (Integration Tests)
            ↓
          Task 7.3 (Property Tests)
            ↓
          Task 7.4 (Documentation)
            ↓
          Task 7.5 (Update Steering)
            ↓
        Phase 8: Migration
          Task 8.1 (Migrate Remaining)
            ↓
          Task 8.2 (Document Tongyi)
```

## Effort Summary

| Phase | Tasks | Backend Effort | Frontend Effort | Documentation Effort | Total Effort |
|-------|-------|----------------|-----------------|---------------------|--------------|
| Phase 1: Backend Foundation | 4 | 10 hours | 0 hours | 2 hours | 12 hours |
| Phase 2: Google Provider (Backend) | 5 | 16 hours | 0 hours | 2 hours | 18 hours |
| Phase 3: Frontend Integration | 3 | 0 hours | 10 hours | 0 hours | 10 hours |
| Phase 4: Qwen Provider (Backend) | 2 | 7 hours | 0 hours | 0 hours | 7 hours |
| Phase 5: Ollama Provider (Backend) | 2 | 7 hours | 0 hours | 0 hours | 7 hours |
| Phase 6: Error Handling (Backend) | 2 | 7 hours | 0 hours | 0 hours | 7 hours |
| Phase 7: Testing & Documentation | 5 | 20 hours | 0 hours | 0 hours | 20 hours |
| Phase 8: Migration & Cleanup | 2 | 9 hours | 0 hours | 0 hours | 9 hours |
| **Total** | **25** | **76 hours** | **10 hours** | **4 hours** | **90 hours** |

## Priority Breakdown

| Priority | Tasks | Effort |
|----------|-------|--------|
| P0 (Blocking) | 4 | 12 hours |
| P1 (High) | 12 | 49 hours |
| P2 (Medium) | 6 | 18 hours |
| P3 (Low) | 3 | 13 hours |

## Recommended Implementation Order

1. **Week 1**: Phase 1 (Backend Foundation + Documentation) - 12 hours
   - Task 1.0: Add Python interfaces to design.md (2 hours)
   - Task 1.1: Enhance provider config (3 hours)
   - Task 1.2: Add client caching to factory (4 hours)
   - Task 1.3: Implement client selector (3 hours)
2. **Week 2-3**: Phase 2 (Google Provider Backend + API Docs) - 18 hours
3. **Week 4**: Phase 3 (Frontend Integration) - 10 hours
4. **Week 5**: Phase 4 (Qwen Provider Backend) - 7 hours
5. **Week 6**: Phase 5 (Ollama Provider Backend) + Phase 6 (Error Handling) - 14 hours
6. **Week 7-8**: Phase 7 (Testing & Documentation) - 20 hours
7. **Week 9**: Phase 8 (Migration & Cleanup) - 9 hours

**Total Timeline**: 9 weeks (assuming 10 hours/week)

## Success Criteria

- [ ] Backend is SSOT for all provider configuration
- [ ] Frontend routes all provider operations through backend APIs
- [ ] Google, Qwen, and Ollama support dual-client mode
- [ ] All unit tests pass (>90% coverage)
- [ ] All integration tests pass
- [ ] All property-based tests pass
- [ ] Developer documentation complete
- [ ] No breaking changes to existing functionality
- [ ] Performance metrics maintained or improved
- [ ] Tongyi mixed-mode documented and stable

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing handlers | High | Maintain backward compatibility, gradual migration |
| Performance regression | Medium | Implement client caching, lazy initialization |
| Complex dual-client logic | Medium | Follow backend patterns, comprehensive testing |
| Incomplete capability detection | Low | Fallback to static configuration |
| Documentation drift | Low | Update docs alongside code changes |
| Frontend SDK removal breaks features | High | Thorough testing before removing SDK dependencies |

## Key Differences from Original tasks.md

1. **Backend as SSOT**: All provider logic moved to backend
2. **Frontend as thin client**: Frontend only calls backend APIs
3. **No frontend provider SDK**: Google SDK removed from frontend
4. **Tongyi exception**: Mixed-mode documented and deferred
5. **Configuration-driven**: Single Python dict for all providers (not YAML/JSON)
6. **API endpoints**: New backend endpoints for Google modes
7. **Template loading**: Frontend loads provider config from backend
8. **Reduced frontend effort**: 10 hours vs 37 hours (73% reduction)
9. **Increased backend effort**: 76 hours vs 44 hours (73% increase)
10. **Added documentation tasks**: 4 hours for Python interfaces and API docs
11. **Total effort**: 90 hours vs 81 hours (11% increase)
12. **Dual-client clarification**: Marked as optional feature (only Qwen/Ollama)
13. **Client caching**: Added explicit task for missing caching mechanism

The architecture shift to backend-as-SSOT simplifies frontend code and centralizes provider logic, making the system more maintainable and extensible.

## Analysis Issues Addressed

This updated task list addresses all high-priority issues from `analysis.md`:

### High Priority (P0) ✅
1. **Language inconsistency** (Issue #1): Added Task 1.0 to provide Python interfaces alongside TypeScript
2. **Dual-Client scope unclear** (Issue #2): Clarified in Task 1.1 that dual-client is optional (only Qwen/Ollama)
3. **Client caching missing** (Issue #3): Added explicit caching requirements in Task 1.2

### Medium Priority (P1) ✅
4. **Configuration format** (Issue #4): Documented in Task 1.1 why Python dict is used instead of YAML/JSON
5. **API endpoint list missing** (Issue #5): Added Task 2.5 to document all API endpoints
6. **Error handling flowchart** (Issue #6): Covered in existing Task 6.1 and 6.2

### Implementation Notes
- Python dict configuration provides better type safety and IDE support than YAML/JSON
- Dual-client pattern is an advanced feature, not a requirement for all providers
- Client caching is critical for performance and was missing from original implementation
- API documentation is essential for frontend-backend integration
