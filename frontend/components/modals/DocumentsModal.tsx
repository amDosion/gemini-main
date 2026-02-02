
import React, { useState, useEffect, useRef } from 'react';
import { X, Upload, File, Trash2, Database, AlertCircle, CheckCircle, Loader } from 'lucide-react';
import { DocumentMetadata, VectorStoreStats } from '../../types/types';
import { EmbeddingService } from '../../services/embeddingService';

interface DocumentsModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiKey: string;
  userId: string;
}

export const DocumentsModal: React.FC<DocumentsModalProps> = ({
  isOpen,
  onClose,
  apiKey,
  userId
}) => {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [stats, setStats] = useState<VectorStoreStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [success, setSuccess] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      fetchDocuments();
    }
  }, [isOpen]);

  const fetchDocuments = async () => {
    setIsLoading(true);
    setError('');
    try {
      const result = await EmbeddingService.getUserDocuments(userId);
      if (result.success) {
        setDocuments(result.documents);
        setStats(result.stats);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch documents');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    setError('');
    setSuccess('');

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        setUploadProgress(`Processing ${file.name} (${i + 1}/${files.length})...`);

        // Extract text from file
        const content = await EmbeddingService.extractTextFromFile(file);

        // Add to vector store
        const result = await EmbeddingService.addDocument(
          userId,
          file.name,
          content,
          apiKey
        );

        if (!result.success) {
          throw new Error(result.error || 'Failed to add document');
        }
      }

      setSuccess(`Successfully added ${files.length} document(s)`);
      await fetchDocuments();

      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err: any) {
      setError(err.message || 'Failed to upload documents');
    } finally {
      setIsUploading(false);
      setUploadProgress('');
    }
  };

  const handleDeleteDocument = async (documentId: string) => {
    if (!confirm('Are you sure you want to delete this document?')) {
      return;
    }

    setError('');
    setSuccess('');

    try {
      await EmbeddingService.deleteDocument(userId, documentId);
      setSuccess('Document deleted successfully');
      await fetchDocuments();
    } catch (err: any) {
      setError(err.message || 'Failed to delete document');
    }
  };

  const handleClearAll = async () => {
    if (!confirm('Are you sure you want to clear all documents? This cannot be undone.')) {
      return;
    }

    setError('');
    setSuccess('');

    try {
      await EmbeddingService.clearAllDocuments(userId);
      setSuccess('All documents cleared');
      await fetchDocuments();
    } catch (err: any) {
      setError(err.message || 'Failed to clear documents');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 rounded-2xl border border-slate-800 shadow-2xl max-w-2xl w-full max-h-[80vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-teal-500/10 rounded-lg">
              <Database className="text-teal-400" size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Document Vector Store</h2>
              <p className="text-sm text-slate-400">Manage documents for RAG</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-800 transition-colors text-slate-400 hover:text-white"
          >
            <X size={20} />
          </button>
        </div>

        {/* Stats */}
        {stats && (
          <div className="px-6 py-4 bg-slate-950/50 border-b border-slate-800">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-sm text-slate-400">Total Documents</div>
                <div className="text-2xl font-bold text-white">{stats.totalDocuments}</div>
              </div>
              <div>
                <div className="text-sm text-slate-400">Total Chunks</div>
                <div className="text-2xl font-bold text-white">{stats.totalChunks}</div>
              </div>
            </div>
          </div>
        )}

        {/* Messages */}
        {error && (
          <div className="mx-6 mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-start gap-2">
            <AlertCircle className="text-red-400 flex-shrink-0 mt-0.5" size={16} />
            <span className="text-red-400 text-sm">{error}</span>
          </div>
        )}

        {success && (
          <div className="mx-6 mt-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg flex items-start gap-2">
            <CheckCircle className="text-green-400 flex-shrink-0 mt-0.5" size={16} />
            <span className="text-green-400 text-sm">{success}</span>
          </div>
        )}

        {/* Upload Section */}
        <div className="p-6 border-b border-slate-800">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".txt,.md,text/*"
            onChange={handleFileUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="w-full p-4 border-2 border-dashed border-slate-700 rounded-xl hover:border-teal-500/50 hover:bg-teal-500/5 transition-all flex items-center justify-center gap-2 text-slate-400 hover:text-teal-400 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isUploading ? (
              <>
                <Loader className="animate-spin" size={20} />
                <span>{uploadProgress}</span>
              </>
            ) : (
              <>
                <Upload size={20} />
                <span>Click to upload documents (.txt, .md)</span>
              </>
            )}
          </button>
          <p className="text-xs text-slate-500 mt-2 text-center">
            Documents will be chunked and vectorized for semantic search
          </p>
        </div>

        {/* Documents List */}
        <div className="flex-1 overflow-auto p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader className="animate-spin text-slate-400" size={32} />
            </div>
          ) : documents.length === 0 ? (
            <div className="text-center py-12">
              <File className="mx-auto text-slate-600 mb-3" size={48} />
              <p className="text-slate-400">No documents uploaded yet</p>
              <p className="text-slate-500 text-sm mt-1">Upload documents to start using RAG</p>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <div
                  key={doc.documentId}
                  className="flex items-center justify-between p-4 bg-slate-950/50 rounded-lg border border-slate-800 hover:border-slate-700 transition-colors"
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <File className="text-teal-400 flex-shrink-0" size={20} />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-white truncate">{doc.filename}</div>
                      <div className="text-xs text-slate-500">
                        {doc.chunkCount} chunks • Added {new Date(doc.addedAt).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteDocument(doc.documentId)}
                    className="p-2 rounded-lg hover:bg-red-500/10 text-slate-400 hover:text-red-400 transition-colors"
                    title="Delete document"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-800 flex items-center justify-between">
          <button
            onClick={handleClearAll}
            disabled={documents.length === 0}
            className="px-4 py-2 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            Clear All
          </button>
          <button
            onClick={onClose}
            className="px-6 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white transition-colors font-medium"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
