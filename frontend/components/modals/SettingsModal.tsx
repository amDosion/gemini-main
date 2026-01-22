
import React, { useState, useEffect } from 'react';
import { X, Database, Edit3, Cloud, Image } from 'lucide-react';
import { ConfigProfile } from '../../services/db';
import { StorageConfig } from '../../types/storage';
import { ProfilesTab } from './settings/ProfilesTab';
import { EditorTab } from './settings/EditorTab';
import { StorageTab } from './settings/StorageTab';
import { StorageEditorTab } from './settings/StorageEditorTab';
import { VertexAIConfiguration } from './settings/VertexAIConfiguration';
interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  profiles: ConfigProfile[];
  activeProfileId: string | null;
  onSaveProfile: (profile: ConfigProfile, autoActivate?: boolean) => Promise<void>;
  onDeleteProfile: (id: string) => Promise<void>;
  onActivateProfile: (id: string) => Promise<void>;

  // 云存储相关
  storageConfigs: StorageConfig[];
  activeStorageId: string | null;
  onSaveStorage: (config: StorageConfig) => Promise<void>;
  onDeleteStorage: (id: string) => Promise<void>;
  onActivateStorage: (id: string) => Promise<void>;

  initialApiKey: string;
  initialBaseUrl: string;
  hiddenModelIds: string[];
  initialTab?: 'profiles' | 'editor' | 'storage' | 'storage-editor' | 'imagen';
}

type SettingsTab = 'profiles' | 'editor' | 'storage' | 'storage-editor' | 'imagen';

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  profiles,
  activeProfileId,
  onSaveProfile,
  onDeleteProfile,
  onActivateProfile,
  storageConfigs,
  activeStorageId,
  onSaveStorage,
  onDeleteStorage,
  onActivateStorage,
  hiddenModelIds,
  initialTab = 'profiles'
}) => {
  const [activeTab, setActiveTab] = useState<SettingsTab>(initialTab);
  const [footerNode, setFooterNode] = useState<HTMLDivElement | null>(null);

  // Track which profile is being edited. Null means "Create New".
  const [editingProfile, setEditingProfile] = useState<ConfigProfile | null>(null);
  const [editingStorage, setEditingStorage] = useState<StorageConfig | null>(null);

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
      // Reset editing state when opening
      if (initialTab !== 'editor') {
        setEditingProfile(null);
      }
      if (initialTab !== 'storage-editor') {
        setEditingStorage(null);
      }
    }
  }, [isOpen, initialTab]);

  const handleStartCreate = () => {
    setEditingProfile(null);
    setActiveTab('editor');
  };

  const handleStartEdit = (profile: ConfigProfile) => {
    setEditingProfile(profile);
    setActiveTab('editor');
  };

  const handleSave = async (profile: ConfigProfile) => {
    // 保存并激活配置（内部只刷新一次）
    await onSaveProfile(profile, true);
    onClose();
  };

  // 云存储相关
  const handleStartCreateStorage = () => {
    setEditingStorage(null);
    setActiveTab('storage-editor');
  };

  const handleStartEditStorage = (storage: StorageConfig) => {
    setEditingStorage(storage);
    setActiveTab('storage-editor');
  };

  const handleSaveStorage = async (storage: StorageConfig) => {
    await onSaveStorage(storage);
    // Auto-activate the new storage for convenience
    await onActivateStorage(storage.id);

    setActiveTab('storage');
  };

  const TabButton = ({ id, icon: Icon, label }: { id: SettingsTab, icon: any, label: string }) => (
    <button
      type="button"
      onClick={() => setActiveTab(id)}
      className={`flex-1 md:flex-none md:w-full flex items-center justify-center md:justify-start gap-2 md:gap-3 px-3 md:px-4 py-2 md:py-3 text-xs md:text-sm font-medium rounded-lg md:rounded-xl transition-all whitespace-nowrap ${activeTab === id
        ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20'
        : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
        }`}
    >
      <Icon size={16} className="md:w-[18px] md:h-[18px]" />
      {label}
    </button>
  );

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] bg-slate-950 flex flex-col md:flex-row overflow-hidden animate-[fadeIn_0.2s_ease-out]">

      {/* Sidebar / Top Nav */}
      <div className="w-full md:w-64 bg-slate-900/50 border-b md:border-b-0 md:border-r border-slate-800 p-2 md:p-4 flex flex-col shrink-0">
        <div className="px-2 md:px-4 py-2 md:py-4 mb-2 md:mb-4 flex items-center justify-between md:block">
          <div>
            <h2 className="text-lg md:text-xl font-bold text-white tracking-tight">Settings</h2>
            <p className="text-[10px] md:text-xs text-slate-500 mt-1 hidden md:block">Configure Providers & Keys</p>
          </div>
          {/* Mobile Close Button (Optional if we want one here, but we have footer close) */}
          <button onClick={onClose} className="md:hidden p-2 text-slate-400 hover:text-white">
            <X size={20} />
          </button>
        </div>
        <nav className="flex flex-row md:flex-col gap-2 overflow-x-auto scrollbar-hide">
          <TabButton id="profiles" icon={Database} label="Configs" />
          <TabButton id="storage" icon={Cloud} label="Storage" />
          <TabButton id="editor" icon={Edit3} label="Editor" />
          <TabButton id="imagen" icon={Image} label="Vertex AI" />
        </nav>
      </div>

      {/* Content Area */}
      <div className="flex-1 flex flex-col min-w-0 bg-slate-950 relative">
        <div className="flex-1 relative">

          {activeTab === 'profiles' && (
            <ProfilesTab
              profiles={profiles}
              activeProfileId={activeProfileId}
              onActivateProfile={onActivateProfile}
              onDeleteProfile={onDeleteProfile}
              onSaveProfile={onSaveProfile} // For duplication updates
              onEditProfile={handleStartEdit}
              onCreateNew={handleStartCreate}
            />
          )}

          {activeTab === 'editor' && (
            <EditorTab
              initialData={editingProfile}
              existingProfiles={profiles}
              onSave={handleSave}
              onClose={onClose}
              footerNode={footerNode}
            />
          )}

          {activeTab === 'storage' && (
            <StorageTab
              storageConfigs={storageConfigs}
              activeStorageId={activeStorageId}
              onSaveStorage={onSaveStorage}
              onDeleteStorage={onDeleteStorage}
              onActivateStorage={onActivateStorage}
              onCreateNew={handleStartCreateStorage}
              onEditStorage={handleStartEditStorage}
            />
          )}

          {activeTab === 'storage-editor' && (
            <StorageEditorTab
              initialData={editingStorage}
              existingConfigs={storageConfigs}
              onSave={handleSaveStorage}
              onClose={() => setActiveTab('storage')}
              footerNode={footerNode}
            />
          )}

          {activeTab === 'imagen' && (
            <VertexAIConfiguration
              footerNode={footerNode}
              onClose={onClose}
            />
          )}

        </div>

        {/* Footer Area - Acts as a Portal Target */}
        <div
          ref={node => setFooterNode(node)}
          className="p-4 md:p-6 border-t border-slate-800 bg-slate-900 flex justify-end gap-3 z-10 sticky bottom-0"
        >
          {/* Default Footer Content (Close Button) for non-editor tabs */}
          {(activeTab === 'profiles' || activeTab === 'storage') && (
            <button
              onClick={onClose}
              className="px-5 py-2.5 rounded-xl text-slate-400 hover:text-white hover:bg-slate-900 transition-colors text-sm font-medium flex items-center gap-1"
            >
              <X size={16} /> Close
            </button>
          )}
          {/* Note: imagen tab uses footerNode portal for its own buttons */}
        </div>
      </div>
    </div>
  );
};
