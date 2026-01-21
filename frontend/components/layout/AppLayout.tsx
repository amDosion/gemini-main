
import React from 'react';
import Sidebar from './Sidebar';
import RightSidebar from './RightSidebar';
import { Header } from './Header';
import { ChatSession, Persona, ModelConfig, AppMode } from '../../types/types';
import { ConfigProfile } from '../../services/db';
import { CacheStatusInfo } from '../../hooks/useCacheStatus';

interface AppLayoutProps {
    children: React.ReactNode;
    // Sidebar Props
    isSidebarOpen: boolean;
    setIsSidebarOpen: (v: boolean) => void;
    sessions: ChatSession[];
    currentSessionId: string | null;
    onNewChat: () => void;
    onSelectSession: (id: string) => void;
    onDeleteSession?: (id: string) => void;
    onUpdateSessionTitle?: (id: string, newTitle: string) => void;
    // 滚动加载相关
    hasMoreSessions?: boolean;
    isLoadingMore?: boolean;
    loadMoreSessions?: () => void;
    // RightSidebar Props
    isRightSidebarOpen: boolean;
    setIsRightSidebarOpen: (v: boolean) => void;
    personas: Persona[];
    activePersonaId: string;
    onSelectPersona: (id: string) => void;
    onCreatePersona: (p: any) => void;
    onUpdatePersona: (id: string, p: any) => void;
    onDeletePersona: (id: string) => void;
    onRefreshPersonas: () => void;
    // Header Props
    isLoadingModels: boolean;
    isModelMenuOpen: boolean;
    setIsModelMenuOpen: (v: boolean) => void;
    activeModelConfig?: ModelConfig;
    configApiKey: string;
    visibleModels: ModelConfig[];
    currentModelId: string;
    onModelSelect: (id: string) => void;
    onOpenSettings: (tab?: any) => void;
    onLogout?: () => void;
    appMode: AppMode;

    // Updated Profile Props
    profiles: ConfigProfile[];
    activeProfileId: string | null;
    onActivateProfile: (id: string) => void;

    // New Props for Settings Injection
    settings?: React.ReactNode;

    // 缓存相关（可选）
    cacheStatus?: CacheStatusInfo;
    onRefreshSessions?: () => void;
}

export const AppLayout: React.FC<AppLayoutProps> = (props) => {
    return (
        <div className="flex h-screen w-screen bg-background text-slate-100 overflow-hidden font-sans">
            <Sidebar
                isOpen={props.isSidebarOpen}
                setIsOpen={props.setIsSidebarOpen}
                sessions={props.sessions}
                currentSessionId={props.currentSessionId}
                onNewChat={props.onNewChat}
                onSelectSession={props.onSelectSession}
                onDeleteSession={props.onDeleteSession}
                onUpdateSessionTitle={props.onUpdateSessionTitle}
                onOpenSettings={() => props.onOpenSettings('profiles')}
                cacheStatus={props.cacheStatus}
                onRefreshSessions={props.onRefreshSessions}
                hasMoreSessions={props.hasMoreSessions}
                isLoadingMore={props.isLoadingMore}
                loadMoreSessions={props.loadMoreSessions}
            />

            {/* Main Content Container (Right Side) */}
            <div className="flex-1 flex flex-col h-full relative min-w-0 bg-slate-950">

                {/* Header is kept outside so it remains visible when settings is open */}
                <Header
                    isSidebarOpen={props.isSidebarOpen}
                    setIsSidebarOpen={props.setIsSidebarOpen}
                    isRightSidebarOpen={props.isRightSidebarOpen}
                    setIsRightSidebarOpen={props.setIsRightSidebarOpen}
                    isLoadingModels={props.isLoadingModels}
                    isModelMenuOpen={props.isModelMenuOpen}
                    setIsModelMenuOpen={props.setIsModelMenuOpen}
                    activeModelConfig={props.activeModelConfig}
                    configApiKey={props.configApiKey}
                    visibleModels={props.visibleModels}
                    currentModelId={props.currentModelId}
                    onModelSelect={props.onModelSelect}
                    onOpenSettings={props.onOpenSettings}
                    appMode={props.appMode}
                    profiles={props.profiles}
                    activeProfileId={props.activeProfileId}
                    onActivateProfile={props.onActivateProfile}
                    onLogout={props.onLogout}
                />

                <div className="flex-1 flex overflow-hidden relative">
                    {/* Center Workspace */}
                    <div className="flex-1 flex flex-col min-w-0 h-full relative">
                        {props.children}
                        {/* Settings renders here now, covering only the workspace/chat area */}
                        {props.settings}
                    </div>

                    <RightSidebar
                        isOpen={props.isRightSidebarOpen}
                        setIsOpen={props.setIsRightSidebarOpen}
                        personas={props.personas}
                        activePersonaId={props.activePersonaId}
                        onSelectPersona={props.onSelectPersona}
                        onCreatePersona={props.onCreatePersona}
                        onUpdatePersona={props.onUpdatePersona}
                        onDeletePersona={props.onDeletePersona}
                        onRefreshPersonas={props.onRefreshPersonas}
                    />
                </div>
            </div>
        </div>
    );
};
