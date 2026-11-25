/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          50: '#F7F6F3',
          100: '#EDEAE3',
          200: '#DDD7CB',
          300: '#C4BBA9',
          400: '#A99D86',
          500: '#8B7C63',
          600: '#6F624D',
          700: '#544A3B',
          800: '#37312A',
          900: '#1C1B19',
          950: '#121110',
        },
        ivory: '#F5F2EC',
        sand: '#E9E2D5',
        gold: {
          100: '#F4EAD7',
          200: '#E7D3AC',
          300: '#D6B87E',
          400: '#C8A35B',
          500: '#B08A4A',
          600: '#92703A',
          700: '#73572E',
        },
        moss: {
          500: '#5E6F5A',
          100: '#E6ECE3',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Playfair Display"', 'Georgia', 'serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(28,27,25,0.04), 0 12px 32px rgba(28,27,25,0.06)',
      },
      borderRadius: {
        xl2: '1.25rem',
      },
    },
  },
  plugins: [],
}
