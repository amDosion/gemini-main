import React, { memo, useState } from 'react';
import {
  BaseEdge,
  EdgeLabelRenderer,
  EdgeProps,
  getBezierPath,
} from 'reactflow';
import { dispatchScopedWorkflowEvent } from './workflowEditorUtils';

const ButtonEdgeComponent: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  selected,
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const handleRemove = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();
    dispatchScopedWorkflowEvent('workflow:remove-edge-request', event.currentTarget, {
      edgeId: String(id),
    });
  };

  const stopPointer = (event: React.MouseEvent | React.PointerEvent) => {
    event.preventDefault();
    event.stopPropagation();
  };
  const showDeleteButton = Boolean(selected || isHovered);

  return (
    <>
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={20}
        style={{ pointerEvents: 'stroke' }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      />
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: selected ? '#22d3ee' : (style as any)?.stroke || '#14b8a6',
          strokeWidth: selected ? 2.5 : (style as any)?.strokeWidth || 2,
        }}
      />
      <EdgeLabelRenderer>
        {showDeleteButton && (
          <div
            className="nodrag nopan pointer-events-auto"
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: 'all',
              zIndex: 20,
            }}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            onPointerDown={stopPointer}
            onMouseDown={stopPointer}
          >
            <button
              type="button"
              className="w-5 h-5 rounded-full border border-slate-500 bg-slate-900/95 text-slate-200 text-[12px] leading-none flex items-center justify-center hover:border-rose-400 hover:text-rose-300 hover:bg-slate-900 transition-colors shadow"
              title="删除连接线"
              aria-label="删除连接线"
              onPointerDown={stopPointer}
              onMouseDown={stopPointer}
              onClick={handleRemove}
            >
              ×
            </button>
          </div>
        )}
      </EdgeLabelRenderer>
    </>
  );
};

export const ButtonEdge = memo(ButtonEdgeComponent);

export default ButtonEdge;
