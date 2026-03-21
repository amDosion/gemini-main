
import React from 'react';
import { Header } from './Header';
import { ChatSession, ModelConfig, AppMode, ModeCatalogItem } from '../../types/types';
import { ConfigProfile } from '../../services/db';
import { CacheStatusInfo } from '../../hooks/useCacheStatus';
import type { User, ChangePasswordData } from '../../services/auth';
import InlineModeNavigation from './InlineModeNavigation';
import { SessionProvider } from '../../contexts/SessionContext';

interface AppLayoutProps {
    children: React.ReactNode;
    // Session Props (now passed via context to children)
    sessions: ChatSession[];
    currentSessionId: string | null;
    onNewChat: () => void;
    onSelectSession: (id: string) => void;
    onDeleteSession?: (id: string) => void;
    onUpdateSessionTitle?: (id: string, newTitle: string) => void;
    hasMoreSessions?: boolean;
    isLoadingMore?: boolean;
    loadMoreSessions?: () => void;
    cacheStatus?: CacheStatusInfo;
    onRefreshSessions?: () => void;
    // Persona View Props
    isPersonaViewOpen: boolean;
    onOpenPersonaView: () => void;
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
    onOpenCloudStorage: () => void;
    onLogout?: () => void;
    appMode: AppMode;
    // Profile Props
    profiles: ConfigProfile[];
    activeProfileId: string | null;
    onActivateProfile: (id: string) => void;
    currentUser: User | null;
    onChangePassword: (data: ChangePasswordData) => Promise<void>;
    // Settings Injection
    settings?: React.ReactNode;
    // Mode Navigation
    showModeNavigation?: boolean;
    setAppMode?: (mode: AppMode) => void;
    modeCatalog?: ModeCatalogItem[];
    // Legacy — kept for compatibility but no longer used for Sidebar
    isSidebarOpen?: boolean;
    setIsSidebarOpen?: (v: boolean) => void;
}

export const AppLayout: React.FC<AppLayoutProps> = (props) => {
    return (
        <SessionProvider
            sessions={props.sessions}
            currentSessionId={props.currentSessionId}
            onNewChat={props.onNewChat}
            onSelectSession={props.onSelectSession}
            onDeleteSession={props.onDeleteSession}
            onUpdateSessionTitle={props.onUpdateSessionTitle}
            cacheStatus={props.cacheStatus}
            onRefreshSessions={props.onRefreshSessions}
            hasMoreSessions={props.hasMoreSessions}
            isLoadingMore={props.isLoadingMore}
            loadMoreSessions={props.loadMoreSessions}
        >
            <div className="flex h-screen w-screen bg-background text-slate-100 overflow-hidden font-sans">
                {/* Main Content Container — full width now (no global sidebar) */}
                <div className="flex-1 flex flex-col h-full relative min-w-0 bg-slate-950">
                    <Header
                        isSidebarOpen={false}
                        setIsSidebarOpen={() => {}}
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
                        currentUser={props.currentUser}
                        onChangePassword={props.onChangePassword}
                        onLogout={props.onLogout}
                    />

                    <div className="flex-1 flex overflow-hidden relative">
                        {/* Center Workspace */}
                        <div className="flex-1 flex flex-col min-w-0 h-full relative">
                            {props.children}
                            {props.settings}
                        </div>

                        {/* Mode Navigation */}
                        {props.showModeNavigation && props.setAppMode && (
                            <InlineModeNavigation
                                currentMode={props.appMode}
                                setMode={props.setAppMode}
                                modeCatalog={props.modeCatalog}
                                onOpenSettings={props.onOpenSettings}
                                onOpenCloudStorage={props.onOpenCloudStorage}
                                isPersonaViewOpen={props.isPersonaViewOpen}
                                onOpenPersonaView={props.onOpenPersonaView}
                            />
                        )}
                    </div>
                </div>
            </div>
        </SessionProvider>
    );
};
