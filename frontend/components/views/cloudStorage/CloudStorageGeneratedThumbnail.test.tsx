// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { CloudStorageGeneratedThumbnail } from './CloudStorageGeneratedThumbnail';

describe('CloudStorageGeneratedThumbnail', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders generated svg placeholders without entering the media cache path', () => {
    render(
      <CloudStorageGeneratedThumbnail
        kind="video"
        ext="mp4"
        alt="video preview placeholder"
        className="thumb"
      />
    );

    const thumbnail = screen.getByRole('img', {
      name: 'video preview placeholder',
    });
    expect(thumbnail.tagName.toLowerCase()).toBe('svg');
    expect(thumbnail.textContent).toContain('MP4');
    expect(thumbnail.getAttribute('src')).toBeNull();
  });
});
