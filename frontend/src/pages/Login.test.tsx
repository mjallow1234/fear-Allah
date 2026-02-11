import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Login from '../pages/Login';

// Mock the auth store
vi.mock('../stores/authStore', () => ({
  useAuthStore: () => ({
    login: vi.fn(),
    isLoading: false,
    error: null,
  }),
}));

describe('Login Component', () => {
  const renderLogin = () => {
    return render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );
  };

  it('renders login form', () => {
    renderLogin();
    expect(screen.getByRole('heading', { name: /fear-allah/i })).toBeInTheDocument();
    expect(screen.getByText(/email or username/i)).toBeInTheDocument();
    expect(screen.getByText(/^password$/i)).toBeInTheDocument();
  });

  it('allows user to type in email field', () => {
    renderLogin();
    // The input is labeled "Email or Username"
    const emailInput = screen.getByRole('textbox');
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    expect(emailInput).toHaveValue('test@example.com');
  });

  it('allows user to type in password field', () => {
    renderLogin();
    // Password input type="password" therefore use query by display value or by placeholder
    // Login component has no placeholder, so query all inputs and pick the password one
    const inputs = document.querySelectorAll('input');
    const passwordInput = Array.from(inputs).find(i => i.type === 'password');
    expect(passwordInput).toBeTruthy();
    fireEvent.change(passwordInput!, { target: { value: 'testpassword' } });
    expect(passwordInput).toHaveValue('testpassword');
  });

  it('has a submit button', () => {
    renderLogin();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });
});
