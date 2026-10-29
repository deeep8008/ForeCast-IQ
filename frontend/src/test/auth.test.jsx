import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LoginPage from '../pages/LoginPage';
import RegisterPage from '../pages/RegisterPage';
import Header from '../components/Header';
import { AuthProvider } from '../context/AuthContext';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  loginUserInBackend: vi.fn(),
  registerUserInBackend: vi.fn(),
  getCurrentUserFromBackend: vi.fn(),
  logoutUserInBackend: vi.fn(),
  fetchHealth: vi.fn().mockResolvedValue({ status: 'ok', dataset_loaded: false }),
}));

describe('Auth System Frontend Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getCurrentUserFromBackend.mockRejectedValue(new Error('Unauthenticated'));
  });

  it('renders LoginPage form controls and performs validation', async () => {
    const onNavigate = vi.fn();
    render(
      <AuthProvider>
        <LoginPage onNavigate={onNavigate} />
      </AuthProvider>
    );

    expect(screen.getByText(/sign in to forecastiq/i)).toBeInTheDocument();
    const emailInput = screen.getByTestId('login-email-input');
    const passwordInput = screen.getByTestId('login-password-input');
    const submitBtn = screen.getByRole('button', { name: /sign in/i });

    // Submit without input -> should show validation error
    fireEvent.click(submitBtn);
    expect(await screen.findByText(/please enter your email address/i)).toBeInTheDocument();

    // Toggle password visibility
    const toggleBtn = screen.getByRole('button', { name: /show password/i });
    expect(passwordInput.type).toBe('password');
    fireEvent.click(toggleBtn);
    expect(passwordInput.type).toBe('text');
  });

  it('handles successful login and navigation', async () => {
    api.loginUserInBackend.mockResolvedValueOnce({
      user: { full_name: 'Jane Doe', email: 'jane@example.com' },
      session_token: 'fake_token'
    });

    const onNavigate = vi.fn();
    render(
      <AuthProvider>
        <LoginPage onNavigate={onNavigate} />
      </AuthProvider>
    );

    const emailInput = screen.getByTestId('login-email-input');
    const passwordInput = screen.getByTestId('login-password-input');
    const submitBtn = screen.getByRole('button', { name: /sign in/i });

    fireEvent.change(emailInput, { target: { value: 'jane@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'Secret123!' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(api.loginUserInBackend).toHaveBeenCalledWith('jane@example.com', 'Secret123!');
      expect(onNavigate).toHaveBeenCalledWith('home');
    }, { timeout: 2000 });
  });

  it('renders RegisterPage form controls and validates password confirmation', async () => {
    const onNavigate = vi.fn();
    render(
      <AuthProvider>
        <RegisterPage onNavigate={onNavigate} />
      </AuthProvider>
    );

    expect(screen.getByText(/create an account/i)).toBeInTheDocument();
    const nameInput = screen.getByTestId('register-name-input');
    const emailInput = screen.getByTestId('register-email-input');
    const pwdInput = screen.getByTestId('register-password-input');
    const confirmInput = screen.getByTestId('register-confirm-password-input');
    const submitBtn = screen.getByRole('button', { name: /create account/i });

    // Mismatched passwords
    fireEvent.change(nameInput, { target: { value: 'John Smith' } });
    fireEvent.change(emailInput, { target: { value: 'john@example.com' } });
    fireEvent.change(pwdInput, { target: { value: 'Password123' } });
    fireEvent.change(confirmInput, { target: { value: 'Mismatch123' } });
    fireEvent.click(submitBtn);

    expect(await screen.findByText(/passwords do not match/i)).toBeInTheDocument();
  });

  it('renders Header with Login and Register buttons when logged out', async () => {
    const onNavigate = vi.fn();
    render(
      <AuthProvider>
        <Header activeTab="overview" onNavigate={onNavigate} />
      </AuthProvider>
    );

    expect(await screen.findByRole('button', { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /register/i })).toBeInTheDocument();
  });

  it('renders Header with User initials and menu when logged in', async () => {
    api.getCurrentUserFromBackend.mockResolvedValueOnce({
      full_name: 'Bhargav Test',
      email: 'bhargav@example.com'
    });

    const onNavigate = vi.fn();
    render(
      <AuthProvider>
        <Header activeTab="overview" onNavigate={onNavigate} />
      </AuthProvider>
    );

    // After session loads
    expect(await screen.findByText('BT')).toBeInTheDocument();
    expect(screen.getByText('Bhargav Test')).toBeInTheDocument();

    // Open user menu
    const menuBtn = screen.getByTestId('user-account-menu-button');
    fireEvent.click(menuBtn);

    const dropdown = screen.getByTestId('user-account-dropdown');
    expect(dropdown).toBeInTheDocument();
    expect(screen.getAllByText('bhargav@example.com').length).toBeGreaterThanOrEqual(1);
    const logoutBtn = screen.getByRole('button', { name: /sign out/i });
    expect(logoutBtn).toBeInTheDocument();
  });
});
