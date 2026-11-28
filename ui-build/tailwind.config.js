const daisyui = require('daisyui');

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['../templates/**/*.html'],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          '"Segoe UI"',
          'Roboto',
          'sans-serif',
        ],
        mono: ['ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [daisyui],
  daisyui: {
    themes: [
      {
        'converza-dark': {
          'color-scheme': 'dark',
          primary: '#38bdf8',
          'primary-content': '#04202e',
          'base-100': '#0f1419',
          'base-200': '#161c24',
          'base-300': '#222c3a',
          'base-content': '#e6edf3',
          success: '#34d399',
          'success-content': '#04202e',
          error: '#f87171',
          'error-content': '#04202e',
          warning: '#fbbf24',
          'warning-content': '#04202e',
          '--rounded-box': '1rem',
          '--rounded-btn': '0.75rem',
        },
      },
      {
        'converza-light': {
          'color-scheme': 'light',
          primary: '#0284c7',
          'primary-content': '#ffffff',
          'base-100': '#f8fafc',
          'base-200': '#ffffff',
          'base-300': '#e2e8f0',
          'base-content': '#0f172a',
          success: '#059669',
          'success-content': '#ffffff',
          error: '#dc2626',
          'error-content': '#ffffff',
          warning: '#d97706',
          'warning-content': '#ffffff',
          '--rounded-box': '1rem',
          '--rounded-btn': '0.75rem',
        },
      },
    ],
    darkTheme: 'converza-dark',
    logs: false,
  },
};
