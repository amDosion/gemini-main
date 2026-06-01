// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { CloudStorageGeneratedThumbnail } from './CloudStorageGeneratedThumbnail';

describe('CloudStorageGeneratedThumbnail', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders generated data-svg placeholders without entering the media cache path', () => {
    render(
      <CloudStorageGeneratedThumbnail
        kind="video"
        ext="mp4"
        alt="video preview placeholder"
        className="thumb"
      />
    );

    const thumbnail = screen.getByAltText('video preview placeholder');
    expect(thumbnail.getAttribute('src')).toMatch(/^data:image\/svg\+xml;utf8,/);
    expect(decodeURIComponent(thumbnail.getAttribute('src') || '')).toContain('MP4');
    expect(thumbnail.getAttribute('loading')).toBeNull();
  });
});
