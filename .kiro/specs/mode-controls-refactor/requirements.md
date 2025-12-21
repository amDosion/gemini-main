# Requirements Document

## Introduction

本文档定义了模式参数控制组件重构的需求。当前 `GenerationControls.tsx` 文件过于臃肿，混合了多种模式的控制逻辑，需要拆分为独立的模式控制组件，并引入协调者模式统一管理。

## Glossary

- **Mode（模式）**：应用的工作模式，如 `chat`、`image-gen`、`image-edit` 等
- **Controls（控制组件）**：用于调整模式参数的 UI 组件
- **Coordinator（协调者）**：根据当前模式分发渲染对应控制组件的组件
- **AppMode**：类型定义，包含所有支持的模式
- **ControlsState**：控制参数的状态集合

## Requirements

### Requirement 1

**User Story:** As a developer, I want to have separate control components for each mode, so that the codebase is more maintainable and each mode's logic is isolated.

#### Acceptance Criteria

1. WHEN the application mode is `chat`, THE ModeControlsCoordinator SHALL render ChatControls component
2. WHEN the application mode is `image-gen`, THE ModeControlsCoordinator SHALL render ImageGenControls component
3. WHEN the application mode is `image-edit`, THE ModeControlsCoordinator SHALL render ImageEditControls component
4. WHEN the application mode is `image-outpainting`, THE ModeControlsCoordinator SHALL render ImageOutpaintControls component
5. WHEN the application mode is `video-gen`, THE ModeControlsCoordinator SHALL render VideoGenControls component
6. WHEN the application mode is `audio-gen`, THE ModeControlsCoordinator SHALL render AudioGenControls component
7. WHEN the application mode is `pdf-extract`, THE ModeControlsCoordinator SHALL render PdfExtractControls component
8. WHEN the application mode is `virtual-try-on`, THE ModeControlsCoordinator SHALL render VirtualTryOnControls component

### Requirement 2

**User Story:** As a developer, I want a centralized state management hook for all control parameters, so that state logic is separated from UI components.

#### Acceptance Criteria

1. WHEN useControlsState hook is called, THE hook SHALL return all control parameter states and their setters
2. WHEN a control parameter is updated, THE useControlsState hook SHALL update the corresponding state value
3. WHEN the mode changes, THE useControlsState hook SHALL reset mode-specific parameters to default values

### Requirement 3

**User Story:** As a developer, I want reusable shared components for common UI patterns, so that I can avoid code duplication across mode controls.

#### Acceptance Criteria

1. WHEN a toggle button is needed, THE ToggleButton shared component SHALL provide consistent styling and behavior
2. WHEN a dropdown selector is needed, THE DropdownSelector shared component SHALL provide consistent menu behavior
3. WHEN a slider control is needed, THE SliderControl shared component SHALL provide consistent range input behavior

### Requirement 4

**User Story:** As a user, I want the refactored controls to behave exactly the same as before, so that my workflow is not disrupted.

#### Acceptance Criteria

1. WHEN using chat mode controls, THE ChatControls component SHALL provide Search, Browse, RAG, Cache, Reasoning, URL Context, and Code toggles
2. WHEN using image-gen mode controls, THE ImageGenControls component SHALL provide Style, Count, Aspect Ratio, Resolution, and Advanced settings
3. WHEN using image-edit mode controls, THE ImageEditControls component SHALL provide Try-On toggle, Aspect Ratio, Resolution, and Advanced settings
4. WHEN using image-outpainting mode controls, THE ImageOutpaintControls component SHALL provide Scale/Offset mode selector and parameters
5. WHEN using video-gen mode controls, THE VideoGenControls component SHALL provide Aspect Ratio and Resolution selectors
6. WHEN using audio-gen mode controls, THE AudioGenControls component SHALL provide Voice selector
7. WHEN using pdf-extract mode controls, THE PdfExtractControls component SHALL provide Template selector and Advanced settings

### Requirement 5

**User Story:** As a developer, I want a clear directory structure, so that I can easily locate and modify mode-specific code.

#### Acceptance Criteria

1. WHEN adding a new mode, THE developer SHALL create a new file in `frontend/controls/modes/` directory
2. WHEN modifying coordinator logic, THE developer SHALL edit files in `frontend/coordinators/` directory
3. WHEN modifying state logic, THE developer SHALL edit `frontend/hooks/useControlsState.ts`
4. WHEN modifying shared UI components, THE developer SHALL edit files in `frontend/controls/shared/` directory

### Requirement 6

**User Story:** As a developer, I want the InputArea component to be simplified, so that it only orchestrates sub-components without containing mode-specific logic.

#### Acceptance Criteria

1. WHEN InputArea renders controls, THE InputArea SHALL delegate to ModeControlsCoordinator without conditional mode checks
2. WHEN InputArea manages state, THE InputArea SHALL use useControlsState hook instead of inline useState calls
