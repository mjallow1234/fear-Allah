// This setup file is intended only for Vitest. Guard so it doesn't run under Playwright
// (Playwright loads project files in Node and importing jest-dom there causes "expect is not defined").
if (typeof (globalThis as any).vi !== 'undefined' || process.env.VITEST) {
  ;(async () => {
    // Import jest-dom matchers and extend Vitest's expect
    const matchers = await import('@testing-library/jest-dom/matchers');
    const vitest = await import('vitest');
    vitest.expect.extend(matchers as any);

    // Cleanup after each test
    const testing = await import('@testing-library/react');
    vitest.afterEach(() => {
      testing.cleanup();
    });

    // Mock window.matchMedia
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => {},
      }),
    });
  })()
}

