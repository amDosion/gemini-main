import { describe, expect, it } from 'vitest';
import type { Edge, Node } from 'reactflow';
import { autoLayoutWorkflow, estimateWorkflowNodeSize } from './workflowUtils';
import type { WorkflowNodeData } from './types';

const createNode = (id: string, type: string, data: Partial<WorkflowNodeData>, x = 0, y = 0): Node<WorkflowNodeData> => ({
  id,
  type,
  position: { x, y },
  data: {
    label: id,
    description: '',
    icon: '🔧',
    iconColor: 'bg-slate-500',
    type,
    ...data,
  } as WorkflowNodeData,
});

describe('autoLayoutWorkflow', () => {
  it('avoids overlap even with high-content sibling nodes', () => {
    const nodes: Node<WorkflowNodeData>[] = [
      createNode('start', 'start', { type: 'start' }, 0, 0),
      createNode('heavy', 'tool', {
        type: 'tool',
        toolName: 'image_generate',
        toolProviderId: 'google',
        toolModelId: 'imagen-3.0-generate-002',
        toolNumberOfImages: 4,
        toolAspectRatio: '16:9',
        toolResolutionTier: '2K',
        toolImageStyle: 'photorealistic',
        toolNegativePrompt: 'blur, distortion, watermark',
        toolPromptExtend: true,
        toolAddMagicSuffix: true,
        toolArgsTemplate: JSON.stringify({
          prompt: 'A highly detailed product hero shot with cinematic lighting',
          must_keep: ['logo', 'product shape', 'materials'],
          avoid: ['text', 'watermark'],
          quality: 'high',
          composition: 'rule of thirds',
          camera: '85mm',
        }),
      }, 0, 0),
      createNode('light', 'tool', {
        type: 'tool',
        toolName: 'text_length',
      }, 0, 20),
      createNode('end', 'end', { type: 'end' }, 0, 0),
    ];

    const edges: Edge[] = [
      { id: 'e1', source: 'start', target: 'heavy' },
      { id: 'e2', source: 'start', target: 'light' },
      { id: 'e3', source: 'heavy', target: 'end' },
      { id: 'e4', source: 'light', target: 'end' },
    ];

    const laidOut = autoLayoutWorkflow(nodes, edges, {
      startX: 0,
      startY: 0,
      columnGap: 100,
      rowGap: 24,
    });

    const heavy = laidOut.find((node) => node.id === 'heavy');
    const light = laidOut.find((node) => node.id === 'light');

    expect(heavy).toBeTruthy();
    expect(light).toBeTruthy();

    const boxes = laidOut.map((node) => {
      const size = estimateWorkflowNodeSize(node as Node<WorkflowNodeData>);
      return {
        id: node.id,
        x: node.position.x,
        y: node.position.y,
        width: size.width,
        height: size.height,
      };
    });

    const overlaps = (
      a: { x: number; y: number; width: number; height: number },
      b: { x: number; y: number; width: number; height: number },
    ) => (
      a.x < b.x + b.width
      && a.x + a.width > b.x
      && a.y < b.y + b.height
      && a.y + a.height > b.y
    );

    for (let i = 0; i < boxes.length; i += 1) {
      for (let j = i + 1; j < boxes.length; j += 1) {
        expect(overlaps(boxes[i], boxes[j]), `nodes ${boxes[i].id} and ${boxes[j].id} should not overlap`).toBe(false);
      }
    }
  });

  it('allocates extra height for nodes with audio/video result previews', () => {
    const mediaNode = createNode('media', 'agent', {
      type: 'agent',
      status: 'completed',
      result: {
        finalOutput: {
          text: '媒体输出完成',
          audioUrl: 'https://cdn.example.com/final.mp3',
          videoUrl: 'https://cdn.example.com/final.mp4',
        },
      },
    });
    const textOnlyNode = createNode('text-only', 'agent', {
      type: 'agent',
      status: 'completed',
      result: {
        finalOutput: {
          text: '纯文本输出完成',
        },
      },
    });

    const mediaSize = estimateWorkflowNodeSize(mediaNode);
    const textOnlySize = estimateWorkflowNodeSize(textOnlyNode);

    expect(mediaSize.height).toBeGreaterThan(textOnlySize.height);
  });
});
