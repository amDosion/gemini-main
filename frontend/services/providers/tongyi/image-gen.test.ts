/**
 * tongyi/image-gen.ts 单元测试
 * 测试多图片响应解析功能
 */
import { describe, it, expect } from 'vitest';
import { parseMultipleImages } from './image-gen';

describe('parseMultipleImages', () => {
  describe('主要路径: output.choices[].message.content[{image}]', () => {
    it('应正确解析单张图片', () => {
      const data = {
        output: {
          choices: [{
            message: {
              content: [{ image: 'https://example.com/image1.png' }]
            }
          }]
        }
      };
      
      const results = parseMultipleImages(data);
      expect(results.length).toBe(1);
      expect(results[0].url).toBe('https://example.com/image1.png');
      expect(results[0].mimeType).toBe('image/png');
    });

    it('应正确解析多张图片（4张）', () => {
      const data = {
        output: {
          choices: [
            { message: { content: [{ image: 'https://example.com/image1.png' }] } },
            { message: { content: [{ image: 'https://example.com/image2.png' }] } },
            { message: { content: [{ image: 'https://example.com/image3.png' }] } },
            { message: { content: [{ image: 'https://example.com/image4.png' }] } }
          ]
        }
      };
      
      const results = parseMultipleImages(data);
      expect(results.length).toBe(4);
      expect(results[0].url).toBe('https://example.com/image1.png');
      expect(results[1].url).toBe('https://example.com/image2.png');
      expect(results[2].url).toBe('https://example.com/image3.png');
      expect(results[3].url).toBe('https://example.com/image4.png');
    });

    it('应正确解析单个 choice 中的多张图片', () => {
      const data = {
        output: {
          choices: [{
            message: {
              content: [
                { image: 'https://example.com/image1.png' },
                { image: 'https://example.com/image2.png' }
              ]
            }
          }]
        }
      };
      
      const results = parseMultipleImages(data);
      expect(results.length).toBe(2);
    });

    it('应忽略非图片内容', () => {
      const data = {
        output: {
          choices: [{
            message: {
              content: [
                { text: 'Some text' },
                { image: 'https://example.com/image1.png' },
                { audio: 'https://example.com/audio.mp3' }
              ]
            }
          }]
        }
      };
      
      const results = parseMultipleImages(data);
      expect(results.length).toBe(1);
      expect(results[0].url).toBe('https://example.com/image1.png');
    });
  });

  describe('备用路径: output.results[].url', () => {
    it('应正确解析备用格式的单张图片', () => {
      const data = {
        output: {
          results: [{ url: 'https://example.com/image1.png' }]
        }
      };
      
      const results = parseMultipleImages(data);
      expect(results.length).toBe(1);
      expect(results[0].url).toBe('https://example.com/image1.png');
    });

    it('应正确解析备用格式的多张图片', () => {
      const data = {
        output: {
          results: [
            { url: 'https://example.com/image1.png' },
            { url: 'https://example.com/image2.png' },
            { url: 'https://example.com/image3.png' }
          ]
        }
      };
      
      const results = parseMultipleImages(data);
      expect(results.length).toBe(3);
    });

    it('主要路径优先于备用路径', () => {
      const data = {
        output: {
          choices: [{
            message: {
              content: [{ image: 'https://example.com/primary.png' }]
            }
          }],
          results: [{ url: 'https://example.com/fallback.png' }]
        }
      };
      
      const results = parseMultipleImages(data);
      expect(results.length).toBe(1);
      expect(results[0].url).toBe('https://example.com/primary.png');
    });
  });

  describe('边界条件', () => {
    it('空响应应返回空数组', () => {
      const results = parseMultipleImages({});
      expect(results).toEqual([]);
    });

    it('无 output 字段应返回空数组', () => {
      const results = parseMultipleImages({ data: 'something' });
      expect(results).toEqual([]);
    });

    it('空 choices 数组应返回空数组', () => {
      const data = { output: { choices: [] } };
      const results = parseMultipleImages(data);
      expect(results).toEqual([]);
    });

    it('空 results 数组应返回空数组', () => {
      const data = { output: { results: [] } };
      const results = parseMultipleImages(data);
      expect(results).toEqual([]);
    });

    it('null 值应安全处理', () => {
      const data = { output: { choices: [null, undefined] } };
      const results = parseMultipleImages(data);
      expect(results).toEqual([]);
    });

    it('缺少 message 字段应安全处理', () => {
      const data = { output: { choices: [{ other: 'data' }] } };
      const results = parseMultipleImages(data);
      expect(results).toEqual([]);
    });

    it('缺少 content 字段应安全处理', () => {
      const data = { output: { choices: [{ message: { role: 'assistant' } }] } };
      const results = parseMultipleImages(data);
      expect(results).toEqual([]);
    });

    it('content 非数组应安全处理', () => {
      const data = { output: { choices: [{ message: { content: 'string' } }] } };
      const results = parseMultipleImages(data);
      expect(results).toEqual([]);
    });
  });
});
