import React from 'react';
import { AdkSessionPanel } from './AdkSessionPanel';

export interface AgentRuntimeSessionPanelProps extends React.ComponentProps<typeof AdkSessionPanel> {}

export const AgentRuntimeSessionPanel: React.FC<AgentRuntimeSessionPanelProps> = (props) => (
  <AdkSessionPanel {...props} />
);

export default AgentRuntimeSessionPanel;
