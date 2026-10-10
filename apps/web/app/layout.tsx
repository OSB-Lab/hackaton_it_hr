import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { JetBrains_Mono } from 'next/font/google';
import './globals.css';

// Фирменный шрифт ФСП (JetBrains Mono, лицензия OFL — свободное использование).
const jetbrains = JetBrains_Mono({
  subsets: ['latin', 'cyrillic'],
  variable: '--font-jetbrains',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'ИТ-подбор · ФСП',
  description:
    'Платформа обратного найма для ИТ: работодатель сам находит специалиста по подтверждённой категории и присылает предложение с зарплатой.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru" className={jetbrains.variable}>
      <body>{children}</body>
    </html>
  );
}
