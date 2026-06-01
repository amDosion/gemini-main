// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../common/CachedImage', () => ({
  CachedImage: ({ src, alt, source, ...props }: any) => (
    <img
      data-testid="cached-template-sample-image"
      data-source-url={source?.url || ''}
      src={`cached:${src}`}
      alt={alt}
      {...props}
    />
  ),
}));

import { TemplatePreviewPanel } from './TemplatePreviewPanel';
import type { WorkflowTemplate } from '../workflowTemplateTypes';

const template: WorkflowTemplate = {
  id: 'template-cache',
  name: 'Template Cache',
  description: 'template with sample result',
  category: 'image',
  tags: ['image'],
  config: { nodes: [], edges: [] },
  createdAt: Date.now(),
  updatedAt: Date.now(),
};

describe('TemplatePreviewPanel media cache integration', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders template sample image urls through the shared cached image component', () => {
    render(
      <TemplatePreviewPanel
        selectedTemplate={template}
        editingTemplateId={null}
        editingTemplateName=""
        setEditingTemplateName={vi.fn()}
        savingTemplateId={null}
        handleSaveTemplateTitle={vi.fn()}
        handleCancelRenameTemplate={vi.fn()}
        handleStartRenameTemplate={vi.fn()}
        canManageTemplate={() => false}
        selectedTemplateHasSampleResult
        selectedTemplateSampleImageUrls={[
          '/api/storage/local-files/workflow/template-sample-1.png',
          '/api/storage/local-files/workflow/template-sample-2.png',
        ]}
        selectedTemplateSampleVideoUrls={[]}
        selectedTemplateSampleAudioUrls={[]}
        selectedTemplateSampleTextPreview=""
        copyFeedback={null}
        templateActionFeedback={null}
      />
    );

    expect(screen.getByAltText('template-sample-1')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/template-sample-1.png'
    );
    expect(screen.getByAltText('template-sample-1')).toHaveAttribute(
      'src',
      'cached:/api/storage/local-files/workflow/template-sample-1.png'
    );
    expect(screen.getByAltText('template-sample-2')).toHaveAttribute(
      'data-source-url',
      '/api/storage/local-files/workflow/template-sample-2.png'
    );
  });
});
