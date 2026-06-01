// @vitest-environment jsdom
import React, { useState } from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createAttachmentFromFile,
  useClipboardAttachments,
} from './useClipboardAttachments';
import {
  __resetMediaCacheForTest,
  releaseMediaObjectUrl,
  retainMediaObjectUrl,
} from '../services/mediaCache';
import { revokeAttachmentObjectUrls } from '../utils/attachmentUrl';
import type { AppMode, Attachment } from '../types/types';

function makeFile(name: string, type: string): File {
  return new File(['payload'], name, { type });
}

function makeClipboardData(files: File[]) {
  return {
    files,
    items: files.map((file) => ({
      kind: 'file',
      type: file.type,
      getAsFile: () => file,
    })),
  };
}

function dispatchPaste(target: HTMLElement, clipboardData: unknown) {
  const event = new Event('paste', { bubbles: true, cancelable: true });
  Object.defineProperty(event, 'clipboardData', { value: clipboardData });
  const preventDefault = vi.spyOn(event, 'preventDefault');
  fireEvent(target, event);
  return preventDefault;
}

function HookHarness({
  mode,
  maxAttachments,
  replaceExisting = false,
  initialAttachments = [],
  onError = vi.fn(),
}: {
  mode: AppMode;
  maxAttachments?: number;
  replaceExisting?: boolean;
  initialAttachments?: Attachment[];
  onError?: (message: string) => void;
}) {
  const [attachments, setAttachments] = useState<Attachment[]>(initialAttachments);
  const { handlePaste } = useClipboardAttachments({
    mode,
    attachments,
    onAttachmentsChange: setAttachments,
    maxAttachments,
    replaceExisting,
    onError,
  });

  return (
    <div>
      <textarea aria-label="prompt" onPaste={handlePaste} />
      <output data-testid="count">{attachments.length}</output>
      <output data-testid="names">{attachments.map((attachment) => attachment.name).join(',')}</output>
      <output data-testid="mime-types">
        {attachments.map((attachment) => attachment.mimeType).join(',')}
      </output>
    </div>
  );
}

describe('useClipboardAttachments', () => {
  beforeEach(() => {
    __resetMediaCacheForTest();
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:clipboard-file'),
      revokeObjectURL: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
    __resetMediaCacheForTest();
    vi.unstubAllGlobals();
  });

  it('leaves plain text paste untouched', () => {
    render(<HookHarness mode="chat" />);
    const textarea = screen.getByLabelText('prompt');

    const preventDefault = dispatchPaste(textarea, {
      files: [],
      items: [
        {
          kind: 'string',
          type: 'text/plain',
          getAsFile: () => null,
        },
      ],
    });

    expect(preventDefault).not.toHaveBeenCalled();
    expect(screen.getByTestId('count')).toHaveTextContent('0');
  });

  it('creates file-backed pasted attachments without allocating preview blob urls', async () => {
    render(<HookHarness mode="image-chat-edit" maxAttachments={2} />);
    const textarea = screen.getByLabelText('prompt');

    const preventDefault = dispatchPaste(textarea, makeClipboardData([makeFile('', 'image/png')]));

    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('1'));
    expect(preventDefault).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('names')).toHaveTextContent(/pasted-image-\d+-1\.png/);
    expect(screen.getByTestId('mime-types')).toHaveTextContent('image/png');
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });

  it('keeps createObjectUrl as an explicit compatibility escape hatch', () => {
    const attachment = createAttachmentFromFile(makeFile('photo.png', 'image/png'), 0, {
      createObjectUrl: true,
      idFactory: () => 'pasted-photo',
    });

    expect(attachment.url).toBe('blob:clipboard-file');
    expect(attachment.tempUrl).toBe('blob:clipboard-file');
  });

  it('filters pasted files by mode', async () => {
    const onError = vi.fn();
    render(<HookHarness mode="pdf-extract" onError={onError} />);
    const textarea = screen.getByLabelText('prompt');

    dispatchPaste(textarea, makeClipboardData([makeFile('photo.png', 'image/png')]));

    await waitFor(() => expect(onError).toHaveBeenCalledWith(expect.stringContaining('不支持的文件类型')));
    expect(screen.getByTestId('count')).toHaveTextContent('0');
  });

  it('can replace the existing attachment for single-file inputs', async () => {
    const existing = {
      id: 'existing',
      name: 'old.pdf',
      mimeType: 'application/pdf',
      file: makeFile('old.pdf', 'application/pdf'),
    };

    render(
      <HookHarness
        mode="pdf-extract"
        maxAttachments={1}
        replaceExisting
        initialAttachments={[existing]}
      />,
    );
    const textarea = screen.getByLabelText('prompt');

    dispatchPaste(textarea, makeClipboardData([makeFile('invoice.pdf', 'application/pdf')]));

    await waitFor(() => expect(screen.getByTestId('count')).toHaveTextContent('1'));
    expect(screen.getByTestId('names')).toHaveTextContent('invoice.pdf');
  });

  it('defers pasted attachment preview revocation while shared media cache retains it', () => {
    vi.useFakeTimers();
    const attachment = createAttachmentFromFile(makeFile('photo.png', 'image/png'), 0, {
      createObjectUrl: true,
      idFactory: () => 'pasted-photo',
    });

    expect(attachment.url).toBe('blob:clipboard-file');

    retainMediaObjectUrl(attachment.url);
    revokeAttachmentObjectUrls(attachment);

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith('blob:clipboard-file');

    releaseMediaObjectUrl(attachment.url);

    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith('blob:clipboard-file');
    vi.runOnlyPendingTimers();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:clipboard-file');
    vi.useRealTimers();
  });
});
