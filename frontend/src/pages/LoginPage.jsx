import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Mail, Lock, Eye, EyeOff, LogIn, ArrowLeft, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

export default function LoginPage({ onNavigate }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setErrorMsg('Please enter your email address.');
      return;
    }

    // Basic email format validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedEmail)) {
      setErrorMsg('Please provide a syntactically valid email address.');
      return;
    }

    if (!password) {
      setErrorMsg('Please enter your password.');
      return;
    }

    setIsSubmitting(true);
    try {
      await login(trimmedEmail, password);
      setSuccessMsg('Authentication successful! Redirecting...');
      setTimeout(() => {
        if (onNavigate) onNavigate('home');
      }, 700);
    } catch (err) {
      setErrorMsg(err.message || 'Invalid email or password.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-md mx-auto py-8 px-4 sm:px-6">
      {/* Back button */}
      <button
        onClick={() => onNavigate && onNavigate('home')}
        className="flex items-center gap-1.5 text-xs font-medium text-[#5F5670] hover:text-[#1F1B2C] mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4 text-[#A294F9]" />
        <span>Back to ForecastIQ Dashboard</span>
      </button>

      {/* Main Card */}
      <div className="bg-white rounded-3xl border border-[#E5D9F2] shadow-xs p-8 sm:p-10">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[#A294F9] to-[#CDC1FF] mx-auto flex items-center justify-center text-white shadow-xs mb-3">
            <LogIn className="w-6 h-6" />
          </div>
          <h1 className="text-2xl font-bold font-heading text-[#1F1B2C]">
            Sign in to ForecastIQ
          </h1>
          <p className="text-xs text-[#5F5670] mt-1">
            Access enterprise forecasting models, dataset management, and planning.
          </p>
        </div>

        {errorMsg && (
          <div 
            data-testid="login-error-alert"
            className="mb-5 p-3.5 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5"
          >
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Sign in error:</span> {errorMsg}
            </div>
          </div>
        )}

        {successMsg && (
          <div 
            data-testid="login-success-alert"
            className="mb-5 p-3.5 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center gap-2.5"
          >
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span className="font-semibold">{successMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4.5" noValidate>
          {/* Email Address */}
          <div>
            <label className="block text-xs font-semibold text-[#1F1B2C] mb-1.5" htmlFor="login-email">
              Email Address
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#8E83A3]">
                <Mail className="w-4 h-4" />
              </div>
              <input
                id="login-email"
                type="email"
                data-testid="login-email-input"
                autoComplete="email"
                placeholder="planner@enterprise.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isSubmitting}
                className="w-full pl-10 pr-3.5 py-2.5 rounded-xl border border-[#CDC1FF] bg-[#F5EFFF]/40 text-xs text-[#1F1B2C] placeholder-[#8E83A3] focus:outline-none focus:ring-2 focus:ring-[#A294F9]/30 focus:border-[#A294F9] transition-all disabled:opacity-50"
              />
            </div>
          </div>

          {/* Password */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-semibold text-[#1F1B2C]" htmlFor="login-password">
                Password
              </label>
            </div>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#8E83A3]">
                <Lock className="w-4 h-4" />
              </div>
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                data-testid="login-password-input"
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                className="w-full pl-10 pr-10 py-2.5 rounded-xl border border-[#CDC1FF] bg-[#F5EFFF]/40 text-xs text-[#1F1B2C] placeholder-[#8E83A3] focus:outline-none focus:ring-2 focus:ring-[#A294F9]/30 focus:border-[#A294F9] transition-all disabled:opacity-50"
              />
              <button
                type="button"
                data-testid="toggle-password-visibility"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-[#8E83A3] hover:text-[#1F1B2C] transition-colors"
                tabIndex={-1}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            data-testid="login-submit-button"
            disabled={isSubmitting}
            className="w-full mt-2 py-3 px-4 rounded-xl bg-[#A294F9] hover:bg-[#8F7EF7] active:bg-[#7D6AEB] text-white font-semibold text-xs tracking-wide shadow-xs transition-colors flex items-center justify-center gap-2 disabled:opacity-60 cursor-pointer disabled:cursor-not-allowed"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-white" />
                <span>Signing in...</span>
              </>
            ) : (
              <>
                <LogIn className="w-4 h-4" />
                <span>Sign In</span>
              </>
            )}
          </button>
        </form>

        {/* Footer switch */}
        <div className="mt-6 pt-5 border-t border-[#F5EFFF] text-center text-xs text-[#5F5670]">
          Don't have an account?{' '}
          <button
            onClick={() => onNavigate && onNavigate('register')}
            className="font-semibold text-[#A294F9] hover:text-[#7D6AEB] hover:underline transition-colors"
          >
            Register here
          </button>
        </div>
      </div>
    </div>
  );
}
