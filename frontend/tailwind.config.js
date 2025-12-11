/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'sidebar': '#1a1d21',
        'main': '#313338',
        'input': '#383a40',
        'accent': '#5865f2',
      },
    },
  },
  plugins: [],
}
