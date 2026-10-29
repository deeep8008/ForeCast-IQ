import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { 
  getCurrentUserFromBackend, 
  loginUserInBackend, 
  registerUserInBackend, 
  logoutUserInBackend 
} from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  // Restore session on application startup
  const refreshUser = useCallback(async () => {
    try {
      setIsLoading(true);
      const currentUser = await getCurrentUserFromBackend();
      setUser(currentUser);
      setAuthError(null);
      return currentUser;
    } catch (err) {
      setUser(null);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (email, password) => {
    setAuthError(null);
    try {
      const res = await loginUserInBackend(email, password);
      if (res?.user) {
        setUser(res.user);
      } else {
        await refreshUser();
      }
      return res;
    } catch (err) {
      setAuthError(err.message || 'Login failed');
      throw err;
    }
  };

  const register = async (fullName, email, password) => {
    setAuthError(null);
    try {
      const res = await registerUserInBackend(fullName, email, password);
      if (res?.user) {
        setUser(res.user);
      } else {
        await refreshUser();
      }
      return res;
    } catch (err) {
      setAuthError(err.message || 'Registration failed');
      throw err;
    }
  };

  const logout = async () => {
    try {
      await logoutUserInBackend();
    } finally {
      setUser(null);
      setAuthError(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        authError,
        login,
        register,
        logout,
        refreshUser
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
