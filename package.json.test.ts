import { describe, it, expect } from 'vitest';
import pkg from './package.json';

describe('package.json', () => {
  it('should have the correct name', () => {
    expect(pkg.name).toBe('gemini-flux-chat-local');
  });

  it('should have a valid version number', () => {
    // Basic check for semantic versioning format
    expect(pkg.version).toMatch(/^\d+\.\d+\.\d+$/);
  });

  it('should have a module type', () => {
    expect(pkg.type).toBe('module');
  });

  describe('scripts', () => {
    it('should contain a dev script', () => {
      expect(pkg.scripts.dev).toContain('concurrently');
      expect(pkg.scripts.dev).toContain('npm run server');
      expect(pkg.scripts.dev).toContain('vite');
    });

    it('should contain a server script', () => {
      expect(pkg.scripts.server).toContain('cd backend');
      expect(pkg.scripts.server).toContain('uvicorn app.main:app');
    });

    it('should contain a build script', () => {
      expect(pkg.scripts.build).toBe('tsc && vite build');
    });

    it('should contain a preview script', () => {
      expect(pkg.scripts.preview).toBe('vite preview');
    });
  });

  describe('dependencies', () => {
    it('should include react', () => {
      expect(pkg.dependencies).toHaveProperty('react');
    });

    it('should include @google/genai', () => {
      expect(pkg.dependencies).toHaveProperty('@google/genai');
    });

    it('should include lucide-react', () => {
      expect(pkg.dependencies).toHaveProperty('lucide-react');
    });

     it('should include react-markdown', () => {
      expect(pkg.dependencies).toHaveProperty('react-markdown');
    });
  });

  describe('devDependencies', () => {
    it('should include typescript', () => {
      expect(pkg.devDependencies).toHaveProperty('typescript');
    });

    it('should include vite', () => {
      expect(pkg.devDependencies).toHaveProperty('vite');
    });

    it('should include @vitejs/plugin-react', () => {
      expect(pkg.devDependencies).toHaveProperty('@vitejs/plugin-react');
    });

    it('should include tailwindcss', () => {
        expect(pkg.devDependencies).toHaveProperty('tailwindcss');
      });
  });
});
