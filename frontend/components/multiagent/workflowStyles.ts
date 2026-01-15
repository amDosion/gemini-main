/**
 * Workflow Editor Styling Utilities (Phase 7)
 * 
 * Centralized styling configurations for consistent theming:
 * - Light theme colors
 * - Node styles
 * - Edge styles
 * - Animation utilities
 */

import { CSSProperties } from 'react';

// Light theme color palette
export const lightTheme = {
  // Background colors
  canvas: '#f9fafb',        // gray-50
  panel: '#ffffff',         // white
  panelBorder: '#e5e7eb',   // gray-200
  
  // Node colors
  nodeBg: '#ffffff',
  nodeBorder: '#e5e7eb',
  nodeBorderSelected: '#3b82f6',  // blue-500
  nodeShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1)',
  nodeShadowHover: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
  nodeShadowSelected: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
  
  // Edge colors
  edgeDefault: '#9ca3af',    // gray-400
  edgeSelected: '#3b82f6',   // blue-500
  edgeHover: '#6b7280',      // gray-500
  
  // Handle colors
  handleDefault: '#3b82f6',  // blue-500
  handleBorder: '#ffffff',
  
  // Text colors
  textPrimary: '#111827',    // gray-900
  textSecondary: '#6b7280',  // gray-500
  textMuted: '#9ca3af',      // gray-400
  
  // Status colors
  statusPending: '#9ca3af',  // gray-400
  statusRunning: '#3b82f6',  // blue-500
  statusCompleted: '#10b981', // green-500
  statusFailed: '#ef4444',   // red-500
};

// Node style configurations
export const nodeStyles = {
  base: {
    width: 220,
    borderRadius: 8,
    borderWidth: 2,
    padding: 12,
    transition: 'all 0.2s ease-in-out',
  },
  
  shadow: {
    default: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
    hover: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
    selected: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  },
  
  border: {
    default: `2px solid ${lightTheme.nodeBorder}`,
    selected: `2px solid ${lightTheme.nodeBorderSelected}`,
    hover: `2px solid ${lightTheme.edgeHover}`,
  },
};

// Edge style configurations
export const edgeStyles = {
  default: {
    stroke: lightTheme.edgeDefault,
    strokeWidth: 2,
    type: 'smoothstep' as const,
  },
  
  selected: {
    stroke: lightTheme.edgeSelected,
    strokeWidth: 3,
  },
  
  animated: {
    strokeDasharray: '5,5',
    animation: 'dashdraw 0.5s linear infinite',
  },
  
  // Smooth bezier curve configuration
  bezier: {
    type: 'default' as const,
    pathOptions: {
      borderRadius: 8,
      offset: 20,
    },
  },
};

// Handle (connection point) styles
export const handleStyles: CSSProperties = {
  width: 12,
  height: 12,
  backgroundColor: lightTheme.handleDefault,
  border: `2px solid ${lightTheme.handleBorder}`,
  borderRadius: '50%',
  transition: 'all 0.2s ease-in-out',
};

// Animation keyframes (to be added to global CSS)
export const animationKeyframes = `
  @keyframes dashdraw {
    to {
      stroke-dashoffset: -10;
    }
  }
  
  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
  }
  
  @keyframes flow {
    0% {
      stroke-dashoffset: 24;
    }
    100% {
      stroke-dashoffset: 0;
    }
  }
`;

// React Flow custom styles
export const reactFlowStyles = {
  background: {
    backgroundColor: lightTheme.canvas,
  },
  
  controls: {
    button: {
      backgroundColor: lightTheme.panel,
      border: `1px solid ${lightTheme.panelBorder}`,
      borderRadius: 4,
      color: lightTheme.textPrimary,
    },
  },
  
  minimap: {
    backgroundColor: lightTheme.panel,
    maskColor: 'rgb(0, 0, 0, 0.1)',
  },
};

// Utility function to get node style based on state
export const getNodeStyle = (selected: boolean, hover: boolean = false): CSSProperties => ({
  ...nodeStyles.base,
  backgroundColor: lightTheme.nodeBg,
  border: selected ? nodeStyles.border.selected : nodeStyles.border.default,
  boxShadow: selected 
    ? nodeStyles.shadow.selected 
    : hover 
      ? nodeStyles.shadow.hover 
      : nodeStyles.shadow.default,
});

// Utility function to get edge style based on state
export const getEdgeStyle = (selected: boolean, animated: boolean = false) => ({
  ...edgeStyles.default,
  ...(selected && edgeStyles.selected),
  ...(animated && edgeStyles.animated),
});
