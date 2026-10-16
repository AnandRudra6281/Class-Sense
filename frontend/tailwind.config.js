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
          950: '#070a12',
          900: '#0b1120',
          850: '#0f172a',
          800: '#15213b',
          700: '#1e293b',
          600: '#334155',
        },
        brand: {
          primary: '#6366f1',
          hover: '#4f46e5',
          glow: 'rgba(99, 102, 241, 0.15)',
        },
      },
    },
  },
  plugins: [],
}
