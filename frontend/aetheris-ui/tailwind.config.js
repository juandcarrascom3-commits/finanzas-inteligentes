/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: '#0c0d12',
          card: '#14161d',
          sidebar: '#111217',
          activeNav: '#20232b',
          accentCyan: '#38e1e7',
          accentPink: '#c850c0',
          accentTeal: '#2dd4bf',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
