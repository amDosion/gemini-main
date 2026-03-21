import React, { useState, useEffect } from 'react';
import { Sparkles, ArrowRight, Lock, ShieldCheck, Mail, User, ArrowLeft } from 'lucide-react';
import { RegisterData } from '../../services/auth';

interface RegisterPageProps {
    onRegister: (data: RegisterData) => Promise<void>;
    onNavigateToLogin: () => void;
    isLoading?: boolean;
    error?: string | null;
    allowRegistration?: boolean;
}

export const RegisterPage: React.FC<RegisterPageProps> = ({ 
    onRegister, 
    onNavigateToLogin,
    isLoading = false,
    error = null,
    allowRegistration = false
}) => {
    // ✅ 如果注册被禁用，重定向到登录页
    useEffect(() => {
        if (!allowRegistration) {
            onNavigateToLogin();
        }
    }, [allowRegistration, onNavigateToLogin]);

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [name, setName] = useState('');
    const [localError, setLocalError] = useState<string | null>(null);

    // 如果注册被禁用，不渲染注册表单
    if (!allowRegistration) {
        return null;
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLocalError(null);

        // 验证
        if (!email || !password || !confirmPassword) {
            setLocalError('Please fill in all required fields');
            return;
        }
        if (password.length < 8) {
            setLocalError('Password must be at least 8 characters');
            return;
        }
        if (password !== confirmPassword) {
            setLocalError('Passwords do not match');
            return;
        }

        try {
            await onRegister({ email, password, confirmPassword, name: name || undefined });
        } catch (err) {
            // Error is handled by parent
        }
    };

    const displayError = localError || error;


    return (
        <div className="min-h-screen w-full bg-slate-950 flex items-center justify-center relative overflow-hidden font-sans selection:bg-indigo-500/30">
            {/* Background Pattern */}
            <div className="absolute inset-0 pointer-events-none">
                <div className="absolute inset-0 opacity-[0.03]" style={{ backgroundImage: 'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
                <div className="absolute top-[-10%] left-[-10%] w-[600px] h-[600px] bg-indigo-600/10 rounded-full blur-[100px] animate-pulse-slow" />
                <div className="absolute bottom-[-10%] right-[-10%] w-[600px] h-[600px] bg-blue-600/10 rounded-full blur-[100px] animate-pulse-slow" style={{ animationDelay: '2s' }} />
            </div>

            {/* Main Card */}
            <div className="relative z-10 w-full max-w-sm px-4">
                <div className="bg-slate-900/80 backdrop-blur-xl border border-slate-800 shadow-2xl rounded-2xl overflow-hidden p-6 relative group transition-all duration-500">
                    <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />

                    <div className="flex flex-col items-center text-center relative z-10">
                        {/* Logo */}
                        <div className="mb-5 relative">
                            <div className="absolute inset-0 bg-indigo-500 blur-2xl opacity-20 rounded-full" />
                            <div className="relative w-14 h-14 flex items-center justify-center shadow-lg shadow-indigo-900/20">
                                <Sparkles className="w-7 h-7 text-indigo-400" />
                            </div>
                        </div>

                        {/* Headings */}
                        <h1 className="text-xl font-bold text-white mb-1.5 tracking-tight">Create Account</h1>
                        <p className="text-slate-400 text-xs mb-6 leading-relaxed max-w-[260px]">
                            Fill in your details to create a new account.
                        </p>

                        {/* Form */}
                        <form onSubmit={handleSubmit} className="w-full space-y-3">
                            {/* Name Input */}
                            <div className="space-y-1 text-left">
                                <label className="text-[10px] uppercase text-slate-500 font-bold tracking-wider ml-1">Name (Optional)</label>
                                <div className="relative group/input">
                                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                        <User className="h-4 w-4 text-slate-500 group-focus-within/input:text-indigo-400 transition-colors" />
                                    </div>
                                    <input type="text" value={name} onChange={(e) => setName(e.target.value)} className="w-full bg-slate-950/50 border border-slate-800 text-white text-sm rounded-lg pl-10 pr-3 py-2.5 outline-none transition-all placeholder:text-slate-600 focus:bg-slate-950 focus:border-indigo-500/50 focus:shadow-[0_0_0_4px_rgba(99,102,241,0.1)]" placeholder="Your name" />
                                </div>
                            </div>


                            {/* Email Input */}
                            <div className="space-y-1 text-left">
                                <label className="text-[10px] uppercase text-slate-500 font-bold tracking-wider ml-1">Email *</label>
                                <div className="relative group/input">
                                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                        <Mail className="h-4 w-4 text-slate-500 group-focus-within/input:text-indigo-400 transition-colors" />
                                    </div>
                                    <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full bg-slate-950/50 border border-slate-800 text-white text-sm rounded-lg pl-10 pr-3 py-2.5 outline-none transition-all placeholder:text-slate-600 focus:bg-slate-950 focus:border-indigo-500/50 focus:shadow-[0_0_0_4px_rgba(99,102,241,0.1)]" placeholder="name@example.com" autoFocus />
                                </div>
                            </div>

                            {/* Password Input */}
                            <div className="space-y-1 text-left">
                                <label className="text-[10px] uppercase text-slate-500 font-bold tracking-wider ml-1">Password *</label>
                                <div className="relative group/input">
                                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                        <Lock className="h-4 w-4 text-slate-500 group-focus-within/input:text-indigo-400 transition-colors" />
                                    </div>
                                    <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full bg-slate-950/50 border border-slate-800 text-white text-sm rounded-lg pl-10 pr-3 py-2.5 outline-none transition-all placeholder:text-slate-600 focus:bg-slate-950 focus:border-indigo-500/50 focus:shadow-[0_0_0_4px_rgba(99,102,241,0.1)]" placeholder="Min 8 characters" />
                                </div>
                            </div>

                            {/* Confirm Password Input */}
                            <div className="space-y-1 text-left">
                                <label className="text-[10px] uppercase text-slate-500 font-bold tracking-wider ml-1">Confirm Password *</label>
                                <div className="relative group/input">
                                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                        <Lock className="h-4 w-4 text-slate-500 group-focus-within/input:text-indigo-400 transition-colors" />
                                    </div>
                                    <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="w-full bg-slate-950/50 border border-slate-800 text-white text-sm rounded-lg pl-10 pr-3 py-2.5 outline-none transition-all placeholder:text-slate-600 focus:bg-slate-950 focus:border-indigo-500/50 focus:shadow-[0_0_0_4px_rgba(99,102,241,0.1)]" placeholder="Repeat password" />
                                </div>
                            </div>

                            {/* Error Message */}
                            {displayError && (
                                <div className="text-[11px] text-red-400 text-center bg-red-500/10 py-2 rounded-md border border-red-500/20 animate-[fadeIn_0.2s_ease-out]">
                                    {displayError}
                                </div>
                            )}

                            {/* Submit Button */}
                            <button type="submit" disabled={isLoading} className="w-full bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white font-medium py-2.5 rounded-lg transition-all shadow-lg shadow-indigo-500/20 flex items-center justify-center gap-2 group/btn disabled:opacity-70 disabled:cursor-not-allowed active:scale-[0.98] mt-2">
                                {isLoading ? (
                                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                ) : (
                                    <>Create Account<ArrowRight className="w-4 h-4 group-hover/btn:translate-x-1 transition-transform" /></>
                                )}
                            </button>
                        </form>

                        {/* Back to Login */}
                        <div className="mt-4 pt-4 border-t border-slate-800/50 w-full">
                            <button onClick={onNavigateToLogin} className="w-full flex items-center justify-center gap-2 text-sm text-slate-400 hover:text-indigo-400 transition-colors">
                                <ArrowLeft className="w-4 h-4" />
                                Back to Sign In
                            </button>
                        </div>
                    </div>
                </div>

                {/* Footer Info */}
                <div className="mt-6 flex flex-col items-center gap-3">
                    <div className="flex items-center gap-2 text-[10px] text-slate-500 uppercase tracking-widest font-medium bg-slate-900/50 px-3 py-1 rounded-full border border-slate-800">
                        <ShieldCheck className="w-3 h-3 text-emerald-500" />
                        Secure Environment
                    </div>
                </div>
            </div>
        </div>
    );
};
