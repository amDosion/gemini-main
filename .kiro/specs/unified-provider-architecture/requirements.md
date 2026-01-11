# Requirements Document

## Introduction

This specification defines the requirements for implementing a **unified Provider Client Architecture** across the system. The **backend is the single source of truth (SSOT)** for provider configuration, client creation, and routing, while the frontend remains a thin API client. The goal is to adopt the flexible, mode-based architecture from the reference backend implementation (`.kiro/specs/꽝옘/image_backend/image_backend/`) and align the frontend with backend-managed templates.

The current provider implementation has several limitations:
1. **Google provider** is tightly coupled to the Handler system, making it difficult to add new modes
2. **No unified client factory** - each provider manages clients differently
3. **No dual-client support** - providers can't easily switch between native SDK and OpenAI-compatible API
4. **Configuration scattered** - provider settings are hardcoded in multiple files

The reference backend demonstrates a cleaner, more extensible architecture using:
- **Mode registries** for provider-specific operations
- **Client factories** for unified client creation
- **Platform routing** for intelligent API selection
- **Configuration-driven** design for easy extensibility

This new architecture will enable:
- ✅ Easy addition of new providers via backend configuration
- ✅ Dual-client support managed in backend (native SDK + OpenAI-compatible fallback)
- ✅ Provider-specific modes (like Google's image operations) implemented server-side
- ✅ Backward compatibility with existing frontend handlers

**Scope note**: Unless explicitly stated otherwise, "THE System" refers to backend-owned services. The frontend consumes `/api/*` endpoints and does not instantiate provider SDKs. Tongyi remains mixed-mode for now (backend chat/models, frontend image proxy).

## Glossary

- **Provider**: An AI service provider (e.g., Google, OpenAI, Qwen, Ollama)
- **Client Type**: The SDK/API type used (native SDK, OpenAI-compatible, custom)
- **Mode**: A provider-specific operation type (e.g., OUTPAINT_IMAGEN, INPAINT_ADD, TRY_ON)
- **Platform**: The API platform variant (e.g., Vertex AI vs Developer API for Google)
- **Handler**: A class that executes a specific mode's logic
- **Client Factory**: A factory that creates and manages client instances for a provider
- **Mode Registry**: A registry that maps mode IDs to handler instances (provider-specific)
- **Routing**: Logic that determines which client/platform to use for a given operation
- **SSOT**: Single Source of Truth - centralized configuration for providers and modes
- **Dual-Client**: A provider that supports both native SDK and OpenAI-compatible API
- **Primary Client**: The preferred client (usually native SDK with full features)
- **Secondary Client**: The fallback client (usually OpenAI-compatible for basic operations)

## Requirements

### Requirement 1: Google Mode Registry

**User Story:** As a developer, I want a centralized registry for Google-specific modes, so that I can easily add new modes without modifying the core Handler system.

#### Acceptance Criteria

1. THE System SHALL provide a GoogleModeRegistry class that maps mode IDs to handler instances
2. WHEN a new Google mode is added, THE System SHALL only require registering the handler in the registry
3. THE GoogleModeRegistry SHALL support querying available modes
4. THE GoogleModeRegistry SHALL validate that all registered handlers implement the required interface
5. THE GoogleModeRegistry SHALL be initialized once at application startup

### Requirement 2: Google Client Factory

**User Story:** As a developer, I want a centralized factory for creating Google GenAI clients, so that client initialization logic is consistent and maintainable.

#### Acceptance Criteria

1. THE System SHALL provide a GoogleClientFactory class that creates GenAI client instances
2. WHEN creating a Vertex AI client, THE System SHALL use project ID and location from configuration
3. WHEN creating a Developer API client, THE System SHALL use the provided API key
4. THE GoogleClientFactory SHALL cache client instances to avoid redundant initialization
5. THE GoogleClientFactory SHALL validate required credentials before creating clients
6. WHEN credentials are missing, THE System SHALL throw a descriptive error

### Requirement 3: Platform Routing

**User Story:** As a developer, I want automatic platform selection based on mode requirements, so that the system uses the correct API (Developer or Vertex) for each operation.

#### Acceptance Criteria

1. THE System SHALL provide a resolvePlatform function that determines which platform to use
2. WHEN a mode supports only Vertex AI, THE System SHALL always use Vertex AI
3. WHEN a mode supports only Developer API, THE System SHALL always use Developer API
4. WHEN a mode supports both platforms, THE System SHALL use the user's preference or default
5. THE System SHALL load platform support configuration from a centralized SSOT file
6. WHEN platform selection fails, THE System SHALL provide a clear error message

### Requirement 4: Mode Handler Interface

**User Story:** As a developer, I want a simple, consistent interface for Google mode handlers, so that implementing new modes is straightforward.

#### Acceptance Criteria

1. THE System SHALL define a GoogleModeHandler interface with an execute method
2. THE execute method SHALL accept a request object, client instance, and platform string
3. THE execute method SHALL return a response object with results
4. THE GoogleModeHandler interface SHALL support both synchronous and asynchronous execution
5. WHEN a handler encounters an error, THE System SHALL throw a descriptive error with context

### Requirement 5: SSOT Configuration

**User Story:** As a developer, I want a centralized configuration file for Google modes, so that mode metadata is easy to maintain and update.

#### Acceptance Criteria
1. THE System SHALL provide a YAML/JSON/Python configuration source for Google modes
1. THE System SHALL provide a YAML or JSON configuration file for Google modes
2. THE configuration SHALL include mode ID, default model, platform support, and UI metadata
3. WHEN the configuration is loaded, THE System SHALL validate all required fields
4. THE System SHALL provide a loader function that parses and caches the configuration
5. WHEN configuration is invalid, THE System SHALL throw a descriptive error at startup

### Requirement 6: Backward Compatibility

**User Story:** As a developer, I want the new Google architecture to be backward compatible, so that existing functionality continues to work without breaking changes.

#### Acceptance Criteria
1. THE System SHALL maintain the existing Handler interface for non-Google providers (frontend)
2. WHEN a Google mode is executed, THE System SHALL route through backend APIs (UnifiedProviderClient)
3. WHEN a non-Google mode is executed, THE System SHALL keep the existing Handler flow and backend routing
4. THE System SHALL not require changes to existing OpenAI, DeepSeek, or other provider handlers beyond routing
5. THE System SHALL maintain the existing ExecutionContext interface for compatibility
5. THE System SHALL maintain the existing ExecutionContext interface for compatibility

### Requirement 7: Error Handling and Logging

**User Story:** As a developer, I want comprehensive error handling and logging, so that I can debug issues quickly.

#### Acceptance Criteria

1. WHEN a Google mode fails, THE System SHALL log the mode ID, platform, and error details
2. WHEN client initialization fails, THE System SHALL log the platform and missing credentials
3. WHEN platform routing fails, THE System SHALL log the mode ID and routing decision
4. THE System SHALL use structured logging with consistent log levels
5. THE System SHALL include request IDs in logs for tracing

### Requirement 8: Extensibility for New Modes

**User Story:** As a developer, I want to easily add new Google-specific modes, so that I can leverage new Gemini API features quickly.

#### Acceptance Criteria

1. WHEN adding a new mode, THE System SHALL only require creating a handler class and updating configuration
2. THE System SHALL not require modifying the mode registry or client factory
3. THE System SHALL automatically discover and register new modes from configuration
4. WHEN a mode is added, THE System SHALL validate its configuration at startup
5. THE System SHALL support hot-reloading of mode configuration in development

### Requirement 9: Testing Support

**User Story:** As a developer, I want the new architecture to be testable, so that I can write unit and integration tests easily.

#### Acceptance Criteria

1. THE GoogleClientFactory SHALL support dependency injection for testing
2. THE GoogleModeRegistry SHALL support mock handlers for testing
3. THE resolvePlatform function SHALL be pure and deterministic for testing
4. THE System SHALL provide test utilities for creating mock clients and handlers
5. THE System SHALL support running tests without real API credentials

### Requirement 10: Documentation and Examples

**User Story:** As a developer, I want clear documentation and examples, so that I can understand and use the new architecture effectively.

#### Acceptance Criteria

1. THE System SHALL provide inline code documentation for all public APIs
2. THE System SHALL include examples of implementing a new Google mode
3. THE System SHALL document the platform routing logic and configuration format
4. THE System SHALL provide migration guide for converting existing Google handlers
5. THE System SHALL include architecture diagrams showing the component relationships

### Requirement 11: Unified Provider Client Factory

**User Story:** As a developer, I want a unified factory for creating provider clients, so that all providers follow the same pattern and new providers are easy to add.

#### Acceptance Criteria

1. THE System SHALL provide a ProviderClientFactory class that creates client instances for any provider
2. WHEN creating a client, THE System SHALL load provider configuration from SSOT
3. THE ProviderClientFactory SHALL support multiple client types (native SDK, OpenAI-compatible, custom)
4. THE ProviderClientFactory SHALL cache client instances per provider and credentials
5. WHEN a provider supports dual clients, THE System SHALL create both primary and secondary clients
6. THE ProviderClientFactory SHALL validate credentials before creating clients

### Requirement 12: Configuration-Driven Provider Registration

**User Story:** As a developer, I want to add new providers by configuration only, so that I don't need to modify factory or registry code.

#### Acceptance Criteria
1. THE System SHALL provide a centralized provider configuration source (YAML/JSON/Python)
1. THE System SHALL provide a YAML/JSON configuration file for all providers
2. THE configuration SHALL include provider ID, client type, base URL, and capabilities
3. WHEN a new provider is added to configuration, THE System SHALL automatically register it
4. THE System SHALL validate provider configuration at startup
5. WHEN configuration is invalid, THE System SHALL throw descriptive errors
6. THE System SHALL support provider-specific settings (e.g., dual-client mode, platform routing)

### Requirement 13: Dual-Client Support

**User Story:** As a developer, I want providers to support both native SDK and OpenAI-compatible API, so that I can use the best client for each operation.

#### Acceptance Criteria

1. WHEN a provider is configured with dual-client mode, THE System SHALL create both clients
2. THE System SHALL provide a client selection strategy based on operation type
3. WHEN an operation requires advanced features, THE System SHALL use the primary client (native SDK)
4. WHEN an operation is basic (chat), THE System SHALL optionally use the secondary client (OpenAI-compatible)
5. THE System SHALL support fallback from primary to secondary client on error
6. THE System SHALL log which client is used for each operation

### Requirement 14: Provider-Specific Mode Registries

**User Story:** As a developer, I want each provider to have its own mode registry, so that provider-specific operations are isolated and maintainable.

#### Acceptance Criteria

1. THE System SHALL support provider-specific mode registries (e.g., GoogleModeRegistry, QwenModeRegistry)
2. WHEN a provider has custom modes, THE System SHALL create a dedicated registry
3. THE System SHALL provide a base ModeRegistry class that all provider registries extend
4. WHEN a mode is executed, THE System SHALL route to the correct provider registry
5. THE System SHALL support providers without custom modes (using generic handlers)

### Requirement 15: Client Selection Strategy

**User Story:** As a developer, I want configurable client selection logic, so that I can optimize which client to use for each operation.

#### Acceptance Criteria

1. THE System SHALL provide a ClientSelector interface for determining which client to use
2. WHEN an operation is requested, THE System SHALL consult the selector
3. THE ClientSelector SHALL consider operation type, client capabilities, and user preferences
4. THE System SHALL support default selection strategies per provider
5. THE System SHALL allow custom selection strategies to be registered
6. WHEN client selection fails, THE System SHALL fall back to primary client

### Requirement 16: Provider Capability Detection

**User Story:** As a developer, I want automatic detection of provider capabilities, so that the system knows which features each provider supports.

#### Acceptance Criteria

1. THE System SHALL detect provider capabilities from configuration or API
2. THE capabilities SHALL include: streaming, function calling, vision, thinking, code execution
3. WHEN a provider doesn't support a capability, THE System SHALL throw a descriptive error
4. THE System SHALL cache capability information to avoid repeated API calls
5. THE System SHALL support dynamic capability detection (e.g., Ollama model capabilities)

### Requirement 17: Unified Error Handling

**User Story:** As a developer, I want consistent error handling across all providers, so that errors are predictable and debuggable.

#### Acceptance Criteria

1. THE System SHALL define a ProviderError base class for all provider errors
2. THE ProviderError SHALL include provider ID, client type, operation, and error context
3. WHEN a client creation fails, THE System SHALL throw a ClientCreationError
4. WHEN an operation fails, THE System SHALL throw an OperationError with details
5. THE System SHALL log all errors with structured context
6. THE System SHALL support error recovery strategies (retry, fallback)

### Requirement 18: Provider Configuration Schema

**User Story:** As a developer, I want a clear configuration schema, so that I know exactly what fields are required for each provider.

#### Acceptance Criteria
1. THE System SHALL define a backend schema for provider configuration; the frontend SHALL define TypeScript types for provider templates
2. THE backend configuration SHALL include: providerId, clientType, baseUrl, defaultModel, capabilities
3. THE configuration SHALL support optional fields: secondaryClientType, secondaryBaseUrl, modes
4. THE System SHALL validate configuration against the schema at startup (backend)
5. WHEN configuration is invalid, THE System SHALL list all validation errors
6. THE frontend SHALL consume provider templates from backend SSOT without duplicating config
7. THE System SHALL provide example configurations for common providers

### Requirement 19: Migration Path for Existing Providers

**User Story:** As a developer, I want a clear migration path, so that I can gradually migrate existing providers to the new architecture.

#### Acceptance Criteria

1. THE System SHALL support both old and new provider architectures simultaneously
2. WHEN a provider is migrated, THE System SHALL route through the new factory
3. WHEN a provider is not migrated, THE System SHALL use the existing implementation
4. THE System SHALL provide migration utilities for converting existing code
5. THE System SHALL not break existing functionality during migration

### Requirement 20: Performance Optimization

**User Story:** As a developer, I want the new architecture to be performant, so that it doesn't slow down the application.

#### Acceptance Criteria

1. THE System SHALL cache client instances to avoid redundant initialization
2. THE System SHALL cache provider configuration after first load
3. THE System SHALL cache capability information with TTL
4. WHEN creating clients, THE System SHALL use lazy initialization where possible
5. THE System SHALL minimize memory usage by sharing clients across operations

### Requirement 21: Tongyi Mixed-Mode Exception (Current State)

**User Story:** As a developer, I want to keep Tongyi's current mixed-mode behavior stable, so that existing functionality continues to work while we optimize later.

#### Acceptance Criteria

1. THE System SHALL keep Tongyi chat/models routed through backend endpoints
2. THE System SHALL keep the existing frontend DashScope proxy flow for Tongyi image generation
3. THE System SHALL treat Tongyi unification as a separate, future phase
