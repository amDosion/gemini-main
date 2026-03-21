import React from 'react';
import { History, PanelLeftClose, PanelLeftOpen, X } from 'lucide-react';
import { SessionSwitcher } from './SessionSwitcher';

interface GenViewLayoutProps {
    // Sidebar slots
    sidebarHeaderIcon?: React.ReactNode;
    sidebarTitle: string | React.ReactNode;
    sidebarExtraHeader?: React.ReactNode;
    sidebar?: React.ReactNode;

    // Main area slots
    main?: React.ReactNode;
    mainOverlay?: React.ReactNode;
    bottom?: React.ReactNode;

    // Mobile Sidebar State (Controlled)
    isMobileHistoryOpen: boolean;
    setIsMobileHistoryOpen: (v: boolean) => void;

    /** 是否隐藏顶部的会话切换器（默认显示） */
    hideSessionSwitcher?: boolean;
}

export const GenViewLayout: React.FC<GenViewLayoutProps> = React.memo(({
    sidebarHeaderIcon,
    sidebarTitle,
    sidebarExtraHeader,
    sidebar,
    main,
    mainOverlay,
    bottom,
    isMobileHistoryOpen,
    setIsMobileHistoryOpen,
    hideSessionSwitcher = false
}) => {
    const MIN_LEFT_SIDEBAR_WIDTH = 280;
    const MAX_LEFT_SIDEBAR_WIDTH = 520;
    const DEFAULT_LEFT_SIDEBAR_WIDTH = 384;
    const LEFT_COLLAPSE_STORAGE_KEY = 'gen-view-layout:left-collapsed';
    const LEFT_WIDTH_STORAGE_KEY = 'gen-view-layout:left-width';
    const [leftSidebarWidth, setLeftSidebarWidth] = React.useState<number>(() => {
        if (typeof window === 'undefined') {
            return DEFAULT_LEFT_SIDEBAR_WIDTH;
        }
        try {
            const raw = Number(window.localStorage.getItem(LEFT_WIDTH_STORAGE_KEY));
            if (!Number.isFinite(raw)) {
                return DEFAULT_LEFT_SIDEBAR_WIDTH;
            }
            return Math.max(MIN_LEFT_SIDEBAR_WIDTH, Math.min(MAX_LEFT_SIDEBAR_WIDTH, raw));
        } catch {
            return DEFAULT_LEFT_SIDEBAR_WIDTH;
        }
    });
    const [isDesktopSidebarCollapsed, setIsDesktopSidebarCollapsed] = React.useState<boolean>(() => {
        if (typeof window === 'undefined') {
            return false;
        }
        try {
            return window.localStorage.getItem(LEFT_COLLAPSE_STORAGE_KEY) === '1';
        } catch {
            return false;
        }
    });

    React.useEffect(() => {
        if (typeof window === 'undefined') {
            return;
        }
        try {
            window.localStorage.setItem(LEFT_COLLAPSE_STORAGE_KEY, isDesktopSidebarCollapsed ? '1' : '0');
        } catch {
            // ignore storage errors
        }
    }, [isDesktopSidebarCollapsed]);

    React.useEffect(() => {
        if (typeof window === 'undefined') {
            return;
        }
        try {
            window.localStorage.setItem(LEFT_WIDTH_STORAGE_KEY, String(leftSidebarWidth));
        } catch {
            // ignore storage errors
        }
    }, [leftSidebarWidth]);

    const activeResizeHandlersRef = React.useRef<{ onMouseMove?: (event: MouseEvent) => void; onMouseUp?: () => void }>({});
    const [isResizingLeftSidebar, setIsResizingLeftSidebar] = React.useState(false);

    const stopResizing = React.useCallback(() => {
        const handlers = activeResizeHandlersRef.current;
        if (handlers.onMouseMove) {
            window.removeEventListener('mousemove', handlers.onMouseMove);
        }
        if (handlers.onMouseUp) {
            window.removeEventListener('mouseup', handlers.onMouseUp);
        }
        activeResizeHandlersRef.current = {};
        if (typeof document !== 'undefined') {
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
        setIsResizingLeftSidebar(false);
    }, []);

    React.useEffect(() => {
        return () => {
            stopResizing();
        };
    }, [stopResizing]);

    const startResizing = React.useCallback((event: React.MouseEvent<HTMLDivElement>) => {
        if (typeof window === 'undefined') {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        if (isDesktopSidebarCollapsed) {
            return;
        }
        stopResizing();

        const startX = event.clientX;
        const startWidth = leftSidebarWidth;

        const onMouseMove = (moveEvent: MouseEvent) => {
            const deltaX = moveEvent.clientX - startX;
            const next = Math.max(
                MIN_LEFT_SIDEBAR_WIDTH,
                Math.min(MAX_LEFT_SIDEBAR_WIDTH, startWidth + deltaX),
            );
            setLeftSidebarWidth(next);
        };
        const onMouseUp = () => {
            stopResizing();
        };

        activeResizeHandlersRef.current = { onMouseMove, onMouseUp };
        setIsResizingLeftSidebar(true);
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
    }, [isDesktopSidebarCollapsed, leftSidebarWidth, stopResizing]);

    return (
        <div className="flex-1 flex h-full bg-slate-950 overflow-hidden relative">

            {/* Mobile Toggle Button (Floating) */}
            <button
                onClick={() => setIsMobileHistoryOpen(true)}
                className="md:hidden absolute top-4 left-4 z-30 p-2.5 bg-slate-900/80 text-slate-300 rounded-xl backdrop-blur-md border border-slate-700 shadow-lg hover:text-white transition-colors animate-[fadeIn_0.5s_ease-out]"
                title="Open History"
            >
                <History size={20} />
            </button>

            {/* Mobile Backdrop */}
            {isMobileHistoryOpen && (
                <div
                    className="absolute inset-0 bg-black/60 backdrop-blur-sm z-30 md:hidden animate-[fadeIn_0.2s_ease-out]"
                    onClick={() => setIsMobileHistoryOpen(false)}
                />
            )}

            {/* LEFT SIDEBAR */}
            {isDesktopSidebarCollapsed && (
                <div className="hidden md:flex relative flex-shrink-0 border-r border-slate-800 bg-slate-900/30">
                    <button
                        onClick={() => setIsDesktopSidebarCollapsed(false)}
                        className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 h-12 w-5 rounded-[5px] border border-slate-700 bg-slate-900/95 text-slate-400 hover:text-white hover:border-slate-500 transition-colors shadow flex items-center justify-center z-30"
                        title="展开左侧面板"
                    >
                        <PanelLeftOpen size={13} />
                    </button>
                </div>
            )}
            <div
                style={{ '--gen-left-sidebar-width': `${leftSidebarWidth}px` } as React.CSSProperties}
                className={`
                w-80 flex-shrink-0 z-40 md:z-0 bg-slate-900 border-r border-slate-800 flex flex-col
                md:w-[var(--gen-left-sidebar-width)]
                absolute inset-y-0 left-0 h-full transition-transform duration-300 ease-in-out
                md:relative md:translate-x-0 md:bg-slate-900/30
                ${isDesktopSidebarCollapsed ? 'md:hidden' : 'md:flex'}
                ${isMobileHistoryOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'}
            `}>
                <div className="hidden md:flex absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 z-30">
                    <button
                        onClick={() => setIsDesktopSidebarCollapsed(true)}
                        className="h-12 w-5 rounded-[5px] border border-slate-700 bg-slate-900/95 text-slate-400 hover:text-white hover:border-slate-500 transition-colors shadow flex items-center justify-center"
                        title="折叠左侧面板"
                    >
                        <PanelLeftClose size={13} />
                    </button>
                </div>
                <div
                    onMouseDown={startResizing}
                    className="hidden md:flex absolute top-0 right-0 h-full w-2 translate-x-1/2 z-20 cursor-col-resize group items-center justify-center"
                    title="拖动调整左侧宽度"
                >
                    <span className={`h-14 w-[2px] rounded-full transition-colors ${
                        isResizingLeftSidebar
                            ? 'bg-teal-400/70'
                            : 'bg-slate-700/40 group-hover:bg-slate-500/65'
                    }`} />
                </div>

                {/* Session Switcher (built-in, opt-out via hideSessionSwitcher) */}
                {!hideSessionSwitcher && <SessionSwitcher />}

                {/* Header */}
                <div className="p-3 border-b border-slate-800 flex items-center justify-between bg-slate-900/50 shrink-0">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2 pl-2">
                        {sidebarHeaderIcon} {sidebarTitle}
                    </span>
                    <div className="flex items-center gap-2">
                        {sidebarExtraHeader}
                        <button
                            onClick={() => setIsMobileHistoryOpen(false)}
                            className="md:hidden p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
                        >
                            <X size={18} />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto custom-scrollbar relative">
                    {sidebar}
                </div>
            </div>

            {/* RIGHT MAIN AREA */}
            <div className="flex-1 flex flex-col min-w-0 bg-slate-950 relative">
                {/* Main Content (Canvas/Grid) */}
                <div className="flex-1 overflow-hidden relative flex flex-col">
                    {main}
                </div>

                {/* Overlays (controls, etc) */}
                {mainOverlay}

                {/* Bottom Input Area */}
                {bottom && (
                    <div className="p-4 md:p-6 bg-gradient-to-t from-slate-950 via-slate-950 to-transparent z-20 shrink-0 border-t border-transparent md:border-none">
                        <div className="mx-auto w-full">
                            {bottom}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
});
