/**
 * @deprecated 此 Hook 已废弃，请使用 useAuth 替代
 * 
 * 迁移指南：
 * - import { useAuth } from './useAuth';
 * - const { login, isLoading, error } = useAuth();
 * - await login({ email, password });
 */
import { useState } from 'react';
import { useAuth } from './useAuth';

interface UseLoginReturn {
    email: string;
    setEmail: (email: string) => void;
    password: string;
    setPassword: (password: string) => void;
    error: string | null;
    successMsg: string | null;
    isLoading: boolean;
    handleLogin: (onLoginSuccess: () => void) => Promise<void>;
}

/**
 * @deprecated 使用 useAuth 替代
 */
export const useLogin = (): UseLoginReturn => {
    const { login, isLoading: authLoading, error: authError } = useAuth();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    const handleLogin = async (onLoginSuccess: () => void) => {
        setError(null);
        setSuccessMsg(null);
        setIsLoading(true);

        try {
            if (!email.trim() || !password.trim()) {
                throw new Error('Please fill in all fields.');
            }

            await login({ email, password });
            setSuccessMsg('Login successful!');
            setTimeout(() => onLoginSuccess(), 300);
        } catch (err: any) {
            setError(err.message || authError || 'An error occurred.');
            setIsLoading(false);
        }
    };

    return {
        email,
        setEmail,
        password,
        setPassword,
        error,
        successMsg,
        isLoading: isLoading || authLoading,
        handleLogin
    };
};
