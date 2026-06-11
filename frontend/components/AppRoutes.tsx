/**
 * App.tsx 顶层路由分发组件。
 *
 * 1:1 抽离自 `App.tsx` L770-809 Routes 块
 * （JIRA-frontend-deep-architecture-split.md #10 — App.tsx < 800 完成）。
 */

import React from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { LoginPage, RegisterPage } from './auth';
import type { LoginData, RegisterData } from '../services/auth';

export interface AppRoutesProps {
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  authError: string | null;
  allowRegistration: boolean;
  login: (data: LoginData) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  mainAppElement: React.ReactNode;
}

export const AppRoutes: React.FC<AppRoutesProps> = ({
  isAuthenticated,
  isAuthLoading,
  authError,
  allowRegistration,
  login,
  register,
  mainAppElement,
}) => {
  const navigate = useNavigate();
  return (
    <Routes>
      <Route
        path="/login"
        element={
          isAuthenticated ? (
            <Navigate to="/" replace />
          ) : (
            <LoginPage
              onLogin={login}
              isLoading={isAuthLoading}
              error={authError}
              allowRegistration={allowRegistration}
              onNavigateToRegister={allowRegistration ? () => navigate('/register') : undefined}
            />
          )
        }
      />
      <Route
        path="/register"
        element={
          isAuthenticated ? (
            <Navigate to="/" replace />
          ) : allowRegistration ? (
            <RegisterPage
              onRegister={register}
              isLoading={isAuthLoading}
              error={authError}
              onNavigateToLogin={() => navigate('/login')}
              allowRegistration={allowRegistration}
            />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route
        path="/*"
        element={isAuthenticated ? mainAppElement : <Navigate to="/login" replace />}
      />
    </Routes>
  );
};
