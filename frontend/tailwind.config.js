/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        finance: {
          bg: '#0B0F19',
          card: '#111827',
          cardHover: '#1F2937',
          border: '#374151',
          accent: '#10B981',
          danger: '#EF4444',
          warning: '#F59E0B',
          info: '#3B82F6',
          purple: '#8B5CF6'
        }
      }
    },
  },
  plugins: [],
}
