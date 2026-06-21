// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  INLINE_UPLOAD_ERROR_EVENT,
  reportInlineUploadError,
  type InlineUploadErrorEventDetail,
} from './uploadHandlers';

describe('reportInlineUploadError', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('dispatches a workflow:inline-upload-error CustomEvent with the resolved message', () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    const received: string[] = [];
    const listener = (event: Event) => {
      const detail = (event as CustomEvent<InlineUploadErrorEventDetail>).detail;
      received.push(detail.message);
    };
    window.addEventListener(INLINE_UPLOAD_ERROR_EVENT, listener);

    reportInlineUploadError('回退消息', new Error('真实失败原因'));

    window.removeEventListener(INLINE_UPLOAD_ERROR_EVENT, listener);
    expect(received).toEqual(['真实失败原因']);
    expect(alertSpy).toHaveBeenCalledTimes(1);
    expect(alertSpy).toHaveBeenCalledWith('真实失败原因');
  });

  it('uses the fallback message when the error has no usable message', () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    const received: string[] = [];
    const listener = (event: Event) => {
      received.push((event as CustomEvent<InlineUploadErrorEventDetail>).detail.message);
    };
    window.addEventListener(INLINE_UPLOAD_ERROR_EVENT, listener);

    reportInlineUploadError('回退消息', 'not-an-error');
    reportInlineUploadError('空消息回退', new Error(''));

    window.removeEventListener(INLINE_UPLOAD_ERROR_EVENT, listener);
    expect(received).toEqual(['回退消息', '空消息回退']);
    expect(alertSpy).toHaveBeenCalledTimes(2);
    expect(alertSpy.mock.calls).toEqual([['回退消息'], ['空消息回退']]);
  });

  it('does not fall back to window.alert when a listener consumes the event', () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    const listener = (event: Event) => {
      event.preventDefault();
    };
    window.addEventListener(INLINE_UPLOAD_ERROR_EVENT, listener);

    reportInlineUploadError('回退消息', new Error('已被消费'));

    window.removeEventListener(INLINE_UPLOAD_ERROR_EVENT, listener);
    expect(alertSpy).not.toHaveBeenCalled();
  });

  it('falls back to window.alert when no listener consumes the event', () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

    reportInlineUploadError('回退消息', new Error('未被消费'));

    expect(alertSpy).toHaveBeenCalledTimes(1);
    expect(alertSpy).toHaveBeenCalledWith('未被消费');
  });
});
