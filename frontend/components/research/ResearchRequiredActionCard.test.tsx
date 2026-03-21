// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ResearchRequiredActionCard from './ResearchRequiredActionCard';

describe('ResearchRequiredActionCard', () => {
  afterEach(() => {
    cleanup();
  });

  it('submits selected option', async () => {
    const submit = vi.fn(async () => undefined);

    render(
      <ResearchRequiredActionCard
        requiredAction={{
          act: { name: 'confirm_scope' },
          inputs: ['最近30天', '最近90天'],
        }}
        onSubmitAction={submit}
      />
    );

    fireEvent.click(screen.getByText('最近30天'));

    await waitFor(() => {
      expect(submit).toHaveBeenCalledWith('最近30天');
    });
  });

  it('submits custom input as parsed json when possible', async () => {
    const submit = vi.fn(async () => undefined);

    render(
      <ResearchRequiredActionCard
        requiredAction={{
          act: { name: 'confirm_scope' },
          inputs: [],
        }}
        onSubmitAction={submit}
      />
    );

    const customInputs = screen.getAllByPlaceholderText('自定义输入（支持 JSON 或纯文本）');
    fireEvent.change(customInputs[customInputs.length - 1], {
      target: { value: '{"range":"30d"}' },
    });
    fireEvent.click(screen.getByText('提交自定义结果'));

    await waitFor(() => {
      expect(submit).toHaveBeenCalledWith({ range: '30d' });
    });
  });
});
