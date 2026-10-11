import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import localFont from 'next/font/local';
import './globals.css';

// Фирменный шрифт ФСП — JetBrains Mono (брендбук ФСП, лицензия OFL).
// Файлы лежат в app/fonts, поэтому сборка не зависит от доступа к Google Fonts.
const jetbrainsMono = localFont({
  src: [
    { path: './fonts/JetBrainsMono-Regular.ttf', weight: '400', style: 'normal' },
    { path: './fonts/JetBrainsMono-Medium.ttf', weight: '500', style: 'normal' },
    { path: './fonts/JetBrainsMono-SemiBold.ttf', weight: '600', style: 'normal' },
    { path: './fonts/JetBrainsMono-Bold.ttf', weight: '700', style: 'normal' },
    { path: './fonts/JetBrainsMono-ExtraBold.ttf', weight: '800', style: 'normal' },
  ],
  variable: '--font-jetbrains',
  display: 'swap',
  fallback: ['ui-monospace', 'SFMono-Regular', 'Consolas', 'monospace'],
});

export const metadata: Metadata = {
  title: 'ИТ-подбор · ФСП',
  description:
    'Платформа обратного найма для ИТ: работодатель сам находит специалиста по подтверждённой категории и присылает предложение с зарплатой.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru" className={jetbrainsMono.variable}>
      <body>{children}</body>
    </html>
  );
}
