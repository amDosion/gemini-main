
import React from 'react';
import { Layout } from 'antd';
import { Header as AppHeader } from './Header';
import { ChatSession, ModelConfig, AppMode, ModeCatalogItem } from '../../types/types';
import { ConfigProfile } from '../../services/db';
import { CacheStatusInfo } from '../../hooks/useCacheStatus';
import type { User, ChangePasswordData } from '../../services/auth';
import InlineModeNavigation from './InlineModeNavigation';
import { SessionProvider } from '../../contexts/SessionContext';

const { Sider, Header: LayoutHeader, Content } = Layout;
const SIDEBAR_CLOSED = false;
const noopSetSidebarOpen = () => {};

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
    onOpenSettings: (tab?: string) => void;
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
    workspaceTabs?: React.ReactNode;
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
            <Layout
                data-testid="app-shell"
                className="h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 font-sans"
            >
                {props.showModeNavigation && props.setAppMode && (
                    <Sider
                        role="complementary"
                        aria-label="应用导航"
                        width={104}
                        theme="dark"
                        className="!h-screen !overflow-hidden !bg-slate-950 !border-r !border-slate-800"
                    >
                        <InlineModeNavigation
                            currentMode={props.appMode}
                            setMode={props.setAppMode}
                            modeCatalog={props.modeCatalog}
                            onOpenSettings={props.onOpenSettings}
                            onOpenCloudStorage={props.onOpenCloudStorage}
                            isPersonaViewOpen={props.isPersonaViewOpen}
                            onOpenPersonaView={props.onOpenPersonaView}
                        />
                    </Sider>
                )}

                <Layout className="h-screen min-w-0 bg-slate-950">
                    <LayoutHeader className="!h-14 !p-0 !leading-normal !bg-transparent">
                        <AppHeader
                            isSidebarOpen={SIDEBAR_CLOSED}
                            setIsSidebarOpen={noopSetSidebarOpen}
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
                    </LayoutHeader>
                    {props.workspaceTabs}

                    <Content
                        data-testid="app-content"
                        className="min-h-0 overflow-hidden bg-slate-950"
                    >
                        <div className="flex h-full min-w-0 flex-col relative">
                            {props.children}
                            {props.settings}
                        </div>
                    </Content>
                </Layout>
            </Layout>
        </SessionProvider>
    );
};
