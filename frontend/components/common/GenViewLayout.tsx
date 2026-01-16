import React from 'react';
import { History, X } from 'lucide-react';

interface GenViewLayoutProps {
    // Sidebar slots
    sidebarHeaderIcon?: React.ReactNode;
    sidebarTitle: string | React.ReactNode;
    sidebarExtraHeader?: React.ReactNode; // Extra buttons in header
    sidebar?: React.ReactNode; // Sidebar content slot

    // Main area slots
    main?: React.ReactNode; // Main content slot
    mainOverlay?: React.ReactNode; // Overlay slot
    bottom?: React.ReactNode; // Bottom input area slot

    // Mobile Sidebar State (Controlled)
    isMobileHistoryOpen: boolean;
    setIsMobileHistoryOpen: (v: boolean) => void;
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
    setIsMobileHistoryOpen
}) => {
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
            <div className={`
                w-80 md:w-96 flex-shrink-0 z-40 md:z-0 bg-slate-900 border-r border-slate-800 flex flex-col
                absolute inset-y-0 left-0 h-full transition-transform duration-300 ease-in-out
                md:relative md:translate-x-0 md:bg-slate-900/30
                ${isMobileHistoryOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'}
            `}>
                {/* Header */}
                <div className="p-3 border-b border-slate-800 flex items-center justify-between bg-slate-900/50 min-h-[57px] shrink-0">
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
                        <div className="max-w-4xl mx-auto w-full">
                            {bottom}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
});
