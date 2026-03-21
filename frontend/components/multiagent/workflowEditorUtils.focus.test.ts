// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import {
  applySingleEdgeSelection,
  applySingleNodeSelection,
  isKeyboardEventWithinEditableContext,
  NODE_DEFAULT_FOCUS_FIELD_BY_TYPE,
} from './workflowEditorUtils';

describe('NODE_DEFAULT_FOCUS_FIELD_BY_TYPE', () => {
  it('uses visible textarea fields for media input nodes', () => {
    expect(NODE_DEFAULT_FOCUS_FIELD_BY_TYPE.input_image).toBe('startImageUrls');
    expect(NODE_DEFAULT_FOCUS_FIELD_BY_TYPE.input_video).toBe('startVideoUrls');
    expect(NODE_DEFAULT_FOCUS_FIELD_BY_TYPE.input_audio).toBe('startAudioUrls');
    expect(NODE_DEFAULT_FOCUS_FIELD_BY_TYPE.input_file).toBe('startFileUrls');
  });
});

describe('selection helpers', () => {
  it('keeps single selected node/edge', () => {
    const nodes = applySingleNodeSelection([
      { id: 'n1', position: { x: 0, y: 0 }, data: {}, selected: true },
      { id: 'n2', position: { x: 100, y: 0 }, data: {}, selected: false },
    ] as any, 'n2');
    expect(nodes[0].selected).toBe(false);
    expect(nodes[1].selected).toBe(true);

    const edges = applySingleEdgeSelection([
      { id: 'e1', source: 'n1', target: 'n2', selected: true },
      { id: 'e2', source: 'n2', target: 'n1', selected: false },
    ] as any, 'e2');
    expect(edges[0].selected).toBe(false);
    expect(edges[1].selected).toBe(true);
  });
});

describe('isKeyboardEventWithinEditableContext', () => {
  it('returns true for input and contenteditable descendants', () => {
    const input = document.createElement('input');
    expect(isKeyboardEventWithinEditableContext({
      target: input,
      composedPath: () => [input, document.body],
    } as any)).toBe(true);

    const editable = document.createElement('div');
    editable.setAttribute('contenteditable', 'true');
    const child = document.createElement('span');
    editable.appendChild(child);
    expect(isKeyboardEventWithinEditableContext({
      target: child,
      composedPath: () => [child, editable, document.body],
    } as any)).toBe(true);
  });

  it('uses composedPath and ignores non-editable targets', () => {
    const plain = document.createElement('div');
    expect(isKeyboardEventWithinEditableContext({
      target: plain,
      composedPath: () => [plain, document.body],
    } as any)).toBe(false);

    const textbox = document.createElement('div');
    textbox.setAttribute('role', 'textbox');
    expect(isKeyboardEventWithinEditableContext({
      target: plain,
      composedPath: () => [plain, textbox, document.body],
    } as any)).toBe(true);
  });
});
