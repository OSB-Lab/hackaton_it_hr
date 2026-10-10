import Link from 'next/link';
import { Logo } from './_components/ui';

const STEPS = [
  {
    title: 'Тест вместо резюме',
    text: 'Кандидат выбирает специализацию и грейд и подтверждает их тестом. Так формируется категория.',
  },
  {
    title: 'Работодатель ищет сам',
    text: 'Он описывает потребность, смотрит подборку по категориям и видит подтверждённые достижения ФСП.',
  },
  {
    title: 'Предложение с зарплатой',
    text: 'Условия видны сразу. Контакты кандидата открываются только после того, как он принял предложение.',
  },
];

export default function Home() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-5 py-6">
        <Logo />
        <Link href="/login" className="text-sm font-semibold text-brand hover:underline">
          Войти
        </Link>
      </header>

      <main className="mx-auto max-w-5xl px-5 pb-16 pt-10 sm:pt-16">
        <h1 className="max-w-3xl text-3xl font-bold leading-tight sm:text-5xl">
          Не откликайтесь вслепую. Пусть работодатель найдёт вас сам.
        </h1>
        <p className="mt-6 max-w-2xl text-base leading-relaxed text-ink/70">
          Платформа для ИТ-специалистов, где категория определяется тестом и достижениями
          Федерации спортивного программирования, а предложение приходит сразу с зарплатой.
        </p>

        <div className="mt-10 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/register?role=candidate"
            className="rounded-lg bg-brand px-6 py-3.5 text-center text-sm font-semibold text-white transition hover:bg-brand-dark"
          >
            Я ищу работу
          </Link>
          <Link
            href="/register?role=employer"
            className="rounded-lg border border-muted bg-white px-6 py-3.5 text-center text-sm font-semibold transition hover:border-brand"
          >
            Я работодатель
          </Link>
        </div>

        <ol className="mt-16 grid gap-4 sm:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="rounded-xl bg-white p-6">
              <span className="text-sm font-bold text-brand">0{index + 1}</span>
              <h2 className="mt-3 text-base font-bold">{step.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-ink/70">{step.text}</p>
            </li>
          ))}
        </ol>
      </main>
    </div>
  );
}
