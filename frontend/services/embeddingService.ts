/**
 * Embedding Service
 *
 * Handles document vectorization and RAG functionality via backend API
 */

import { DocumentMetadata, SearchResult, VectorStoreStats } from '../types/types';

export class EmbeddingService {
  /**
   * Add a document to the vector store
   */
  static async addDocument(
    userId: string,
    filename: string,
    content: string,
    apiKey: string,
    chunkSize: number = 500,
    chunkOverlap: number = 100
  ): Promise<any> {
    try {
      // 通过 Vite 代理访问后端
      const response = await fetch('/api/embedding/add-document', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userId: userId,
          filename,
          content,
          apiKey: apiKey,
          chunkSize: chunkSize,
          chunkOverlap: chunkOverlap,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to add document');
      }

      return await response.json();
    } catch (error) {
      console.error('Error adding document:', error);
      throw error;
    }
  }

  /**
   * Search for relevant document chunks
   */
  static async searchDocuments(
    userId: string,
    query: string,
    apiKey: string,
    topK: number = 3
  ): Promise<{ success: boolean; results: SearchResult[]; count: number }> {
    try {
      // 通过 Vite 代理访问后端
      const response = await fetch('/api/embedding/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userId: userId,
          query,
          apiKey: apiKey,
          topK: topK,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to search documents');
      }

      return await response.json();
    } catch (error) {
      console.error('Error searching documents:', error);
      throw error;
    }
  }

  /**
   * Get all documents for a user
   */
  static async getUserDocuments(
    userId: string
  ): Promise<{ success: boolean; documents: DocumentMetadata[]; stats: VectorStoreStats }> {
    try {
      // 通过 Vite 代理访问后端
      const response = await fetch(`/api/embedding/documents/${userId}`);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to fetch documents');
      }

      return await response.json();
    } catch (error) {
      console.error('Error fetching documents:', error);
      throw error;
    }
  }

  /**
   * Delete a specific document
   */
  static async deleteDocument(userId: string, documentId: string): Promise<{ success: boolean; message: string }> {
    try {
      // 通过 Vite 代理访问后端
      const response = await fetch(`/api/embedding/document/${userId}/${documentId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to delete document');
      }

      return await response.json();
    } catch (error) {
      console.error('Error deleting document:', error);
      throw error;
    }
  }

  /**
   * Clear all documents for a user
   */
  static async clearAllDocuments(userId: string): Promise<{ success: boolean; message: string }> {
    try {
      // 通过 Vite 代理访问后端
      const response = await fetch(`/api/embedding/documents/${userId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to clear documents');
      }

      return await response.json();
    } catch (error) {
      console.error('Error clearing documents:', error);
      throw error;
    }
  }

  /**
   * Check if embedding service is available
   */
  static async checkAvailability(): Promise<boolean> {
    try {
      // 通过 Vite 代理访问后端
      const response = await fetch('/health');
      const data = await response.json();
      return data.embedding === true;
    } catch (error) {
      console.error('Error checking embedding availability:', error);
      return false;
    }
  }

  /**
   * Extract text from a file
   */
  static async extractTextFromFile(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = (e) => {
        const text = e.target?.result as string;
        resolve(text);
      };

      reader.onerror = () => {
        reject(new Error('Failed to read file'));
      };

      // For text files, read as text
      if (file.type.startsWith('text/') || file.name.endsWith('.txt') || file.name.endsWith('.md')) {
        reader.readAsText(file);
      } else {
        reject(new Error('Unsupported file type. Please use text files (.txt, .md)'));
      }
    });
  }
}
