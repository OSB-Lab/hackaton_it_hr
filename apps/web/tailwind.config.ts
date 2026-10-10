import type { Config } from 'tailwindcss';

// Палитра и шрифт — из брендбука ФСП (fsp-russia.ru/press/brandbook).
export default {
  content: ['./app/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#402FFF', dark: '#2F20D6', soft: '#ECEAFF' },
        accent: { DEFAULT: '#EC1D35', dark: '#B80F25' },
        surface: '#EDEDED',
        muted: '#C8C9CA',
        ink: '#1B1C21',
      },
      fontFamily: {
        // --font-jetbrains задаётся в app/layout.tsx через next/font
        sans: ['var(--font-jetbrains)', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config;
