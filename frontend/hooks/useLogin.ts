import { useState } from 'react';

// MOCK DATA
// 供测试使用的模拟账号
export const MOCK_USERS = [
    { email: 'admin@example.com', password: 'password', name: 'Admin User' },
    { email: 'user@test.com', password: '123', name: 'Test User' }
];

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

// 模拟 API 延迟
const simulateApiCall = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export const useLogin = (): UseLoginReturn => {
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
            // 1. Basic Validation
            if (!email.trim() || !password.trim()) {
                throw new Error('Please fill in all fields.');
            }

            // 2. Simulate Network Request
            await simulateApiCall(800);

            // 3. Mock Logic
            const user = MOCK_USERS.find(u => u.email === email && u.password === password);

            if (user) {
                setSuccessMsg(`Welcome back, ${user.name}!`);
                // Wait a bit to show success message before redirecting
                setTimeout(() => {
                    onLoginSuccess();
                }, 500);
            } else {
                throw new Error('Invalid email or password.');
            }
        } catch (err: any) {
            setError(err.message || 'An error occurred.');
            setIsLoading(false); // Stop loading on error
        }
        // Note: We don't stop loading on success immediately to prevent flash before unmount/redirect
    };

    return {
        email,
        setEmail,
        password,
        setPassword,
        error,
        successMsg,
        isLoading,
        handleLogin
    };
};
