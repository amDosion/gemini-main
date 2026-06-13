// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { SearchProcess } from './SearchProcess';

describe('SearchProcess', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders search queries as text', () => {
    render(
      <SearchProcess
        queries={['latest api security guidance']}
        isThinking={false}
      />
    );

    expect(screen.getByText('"latest api security guidance"')).not.toBeNull();
  });

  it('strips active content and attributes from rendered search entry html', () => {
    render(
      <SearchProcess
        queries={[]}
        isThinking={false}
        entryPoint={
          '<div onclick="alert(1)"><a href="javascript:alert(1)">unsafe link</a><img src=x onerror=alert(2) /><span style="color:red">safe text</span><script>alert(3)</script></div>'
        }
      />
    );

    expect(screen.getByText('unsafe link')).not.toBeNull();
    expect(screen.getByText('safe text')).not.toBeNull();
    expect(document.querySelector('script')).toBeNull();
    expect(document.querySelector('img')).toBeNull();
    expect(document.querySelector('a')).toBeNull();
    expect(document.querySelector('[onclick]')).toBeNull();
    expect(document.querySelector('[style]')).toBeNull();
  });
});
