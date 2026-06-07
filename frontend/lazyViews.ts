/**
 * 顶层视图的 React.lazy 包装（代码分割）。
 *
 * 1:1 抽离自 `App.tsx` L22-38（< 800 行合规拆分）。
 *
 * 仅 App.tsx 使用；将 lazy 包装集中此处，主组件不再持有 4 个 dynamic import 块。
 */

import { lazy } from 'react';

export const MultiAgentView = lazy(() =>
  import('./components/views/MultiAgentView').then((m) => ({ default: m.MultiAgentView }))
);

export const StudioView = lazy(() =>
  import('./components/views/StudioView').then((m) => ({ default: m.StudioView }))
);

export const CloudStorageView = lazy(() =>
  import('./components/views/CloudStorageView').then((m) => ({ default: m.CloudStorageView }))
);

export const PersonaManagementView = lazy(() =>
  import('./components/views/PersonaManagementView').then((m) => ({
    default: m.PersonaManagementView,
  }))
);
