import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import api from '../services/api';
import { BrowserRouter } from 'react-router-dom';
import Register from './Register';

vi.mock('../services/api', () => ({
  default: { post: vi.fn() },
}));

describe('Register Component', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('renders register form', () => {
    const { container } = render(
      <BrowserRouter>
        <Register />
      </BrowserRouter>
    );
    expect(screen.getByRole('heading', { name: /register/i })).toBeInTheDocument();
    expect(container.querySelector('input[type="email"]')).toBeTruthy();
    expect(container.querySelector('input[type="text"]')).toBeTruthy();
    expect(container.querySelector('input[type="password"]')).toBeTruthy();
  });

  it('allows typing into form fields', () => {
    const { container } = render(
      <BrowserRouter>
        <Register />
      </BrowserRouter>
    );
    const email = container.querySelector('input[type="email"]') as HTMLInputElement;
    const username = container.querySelector('input[type="text"]') as HTMLInputElement;
    const password = container.querySelector('input[type="password"]') as HTMLInputElement;
    fireEvent.change(email, { target: { value: 'test@example.com' } });
    fireEvent.change(username, { target: { value: 'testuser' } });
    fireEvent.change(password, { target: { value: 'secret' } });
    expect(email).toHaveValue('test@example.com');
    expect(username).toHaveValue('testuser');
    expect(password).toHaveValue('secret');
  });

  it('posts form data to api on submit', async () => {
    // @ts-ignore - api is mocked via vi.mock above
    (api as any).post.mockResolvedValue({ data: { access_token: 'token' } });

    // navigation not asserted here; only confirm API call

    const { container } = render(
      <BrowserRouter>
        <Register />
      </BrowserRouter>
    );
    const email = container.querySelector('input[type="email"]') as HTMLInputElement;
    const username = container.querySelector('input[type="text"]') as HTMLInputElement;
    const password = container.querySelector('input[type="password"]') as HTMLInputElement;
    fireEvent.change(email, { target: { value: 'test@example.com' } });
    fireEvent.change(username, { target: { value: 'testuser' } });
    fireEvent.change(password, { target: { value: 'secret' } });
    fireEvent.click(screen.getByRole('button', { name: /register/i }));

    await waitFor(() => expect(api.post).toHaveBeenCalled());
    // Check that the api.post was called with correct endpoint and payload
    expect(api.post).toHaveBeenCalledWith('/api/auth/register', {
      email: 'test@example.com',
      username: 'testuser',
      password: 'secret',
    });
  });
});
