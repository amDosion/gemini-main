import React from 'react';
import { useAuth } from '../../hooks/useAuth';

interface ProtectedRouteProps {
    children: React.ReactNode;
    fallback?: React.ReactNode;
    onUnauthenticated?: () => void;
}

/**
 * ProtectedRoute - 保护需要认证的路由
 * 
 * 用法:
 * <ProtectedRoute onUnauthenticated={() => navigate('/login')}>
 *   <Dashboard />
 * </ProtectedRoute>
 */
export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
    children,
    fallback,
    onUnauthenticated,
}) => {
    const { isAuthenticated, isLoading } = useAuth();

    // 加载中显示 loading 状态
    if (isLoading) {
        return fallback || (
            <div className="min-h-screen w-full bg-slate-950 flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                    <p className="text-slate-400 text-sm">Loading...</p>
                </div>
            </div>
        );
    }

    // 未认证时触发回调
    React.useEffect(() => {
        if (!isLoading && !isAuthenticated && onUnauthenticated) {
            onUnauthenticated();
        }
    }, [isLoading, isAuthenticated, onUnauthenticated]);

    // 未认证时显示 fallback
    if (!isAuthenticated) {
        return fallback || null;
    }

    // 已认证，渲染子组件
    return <>{children}</>;
};

export default ProtectedRoute;
