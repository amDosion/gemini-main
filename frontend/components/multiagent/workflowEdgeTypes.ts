import type { ComponentType } from 'react';
import { ButtonEdge } from './ButtonEdge';

export const DEFAULT_WORKFLOW_EDGE_TYPE = 'buttonedge';

export const FLOW_EDGE_TYPES: Record<string, ComponentType<any>> = {
  [DEFAULT_WORKFLOW_EDGE_TYPE]: ButtonEdge,
};
