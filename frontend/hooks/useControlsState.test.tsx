// @vitest-environment jsdom
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { describe, expect, it } from 'vitest';

import { useControlsState } from './useControlsState';

const ControlsProbe = () => {
  const controls = useControlsState('image-gen');
  return <div data-testid="quality">{controls.outputCompressionQuality}</div>;
};

describe('useControlsState', () => {
  it('defaults image output compression quality to 100', () => {
    render(<ControlsProbe />);

    expect(screen.getByTestId('quality')).toHaveTextContent('100');
  });
});
