import type { Config } from 'tailwindcss';

// Палитра и шрифт — из брендбука ФСП (fsp-russia.ru/press/brandbook).
export default {
  content: ['./app/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        // Палитра брендбука: фиолетовый, красный, графит, серый, светлый + белый.
        brand: { DEFAULT: '#402FFF', dark: '#2F20D6', soft: '#ECEAFF' },
        accent: { DEFAULT: '#EC1D35', dark: '#B80F25', soft: '#FCEBEE' },
        surface: '#EDEDED',
        canvas: '#FFFFFF',
        muted: '#C8C9CA',
        border: '#D9DADB',
        ink: '#1B1C21',
        // Статусные цвета функциональные, вне палитры бренда (доступные значения).
        success: { DEFAULT: '#1F7A4D', soft: '#E7F6EC' },
        warning: { DEFAULT: '#8A5A00', soft: '#FEF3C7' },
      },
      fontFamily: {
        // Единственный шрифт бренда — JetBrains Mono (см. app/layout.tsx).
        sans: ['var(--font-jetbrains)', 'ui-monospace', 'SFMono-Regular', 'Consolas', 'monospace'],
        mono: ['var(--font-jetbrains)', 'ui-monospace', 'SFMono-Regular', 'Consolas', 'monospace'],
      },
      boxShadow: {
        hard: '8px 8px 0 0 #402FFF',
        card: '0 1px 2px 0 rgba(27,28,33,0.04), 0 8px 24px -12px rgba(27,28,33,0.12)',
      },
      keyframes: {
        // Единственная анимация на странице: предложение появляется под лучшей строкой рейтинга.
        reveal: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'none' },
        },
      },
      animation: {
        reveal: 'reveal 0.7s ease-out 0.9s both',
      },
    },
  },
  plugins: [],
} satisfies Config;
