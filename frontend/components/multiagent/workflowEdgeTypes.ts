import type { EdgeTypes } from 'reactflow';
import { ButtonEdge } from './ButtonEdge';

export const DEFAULT_WORKFLOW_EDGE_TYPE = 'buttonedge';

export const FLOW_EDGE_TYPES: EdgeTypes = {
  [DEFAULT_WORKFLOW_EDGE_TYPE]: ButtonEdge,
};
