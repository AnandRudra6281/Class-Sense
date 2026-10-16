/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#060913',
          900: '#0b1222',
          850: '#0f172a',
          800: '#162238',
          700: '#1e293b',
          600: '#334155',
        },
        brand: {
          primary: '#6366f1',
          hover: '#4f46e5',
          glow: 'rgba(99, 102, 241, 0.15)',
        },
        // Severity Palette: low, medium, high, critical
        severity: {
          low: {
            DEFAULT: '#10b981', // Emerald
            bg: 'rgba(16, 185, 129, 0.12)',
            border: '#059669',
            text: '#34d399',
          },
          medium: {
            DEFAULT: '#06b6d4', // Cyan
            bg: 'rgba(6, 182, 212, 0.12)',
            border: '#0891b2',
            text: '#22d3ee',
          },
          high: {
            DEFAULT: '#f59e0b', // Amber
            bg: 'rgba(245, 158, 11, 0.12)',
            border: '#d97706',
            text: '#fbbf24',
          },
          critical: {
            DEFAULT: '#f43f5e', // Rose
            bg: 'rgba(244, 63, 94, 0.15)',
            border: '#e11d48',
            text: '#fb7185',
          },
        },
      },
    },
  },
  plugins: [],
}
