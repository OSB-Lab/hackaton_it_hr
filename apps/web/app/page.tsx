import Link from 'next/link';
import { NetworkArt } from './_components/NetworkArt';
import { Logo } from './_components/ui';

// Все данные на этой странице — иллюстрация. Реальные кандидаты в рейтинге обезличены.

const ROWS = [
  { rank: 1, id: '4812', test: 94, fsp: '3 соревнования', score: '0.92' },
  { rank: 2, id: '1307', test: 91, fsp: '1 соревнование', score: '0.87' },
  { rank: 3, id: '5560', test: 88, fsp: null, score: '0.81' },
  { rank: 4, id: '0921', test: 85, fsp: '2 соревнования', score: '0.79' },
];

const STEPS = [
  {
    title: 'Кандидат проходит тест',
    text: 'Выбирает специализацию и грейд и подтверждает их тестом, а не резюме.',
  },
  {
    title: 'Система присваивает категорию',
    text: 'Специализация и грейд складываются в категорию, например «Backend · Middle». Внутри неё выше стоят те, у кого сильнее подтверждённый профиль и есть достижения ФСП.',
  },
  {
    title: 'Работодатель выбирает из подборки',
    text: 'Описывает, кого ищет, и видит рекомендованных кандидатов с объяснением, почему они подходят.',
  },
  {
    title: 'Предложение приходит с зарплатой',
    text: 'В предложении указана вилка «от–до» в рублях. Контакты кандидата открываются работодателю только после того, как кандидат его принял.',
  },
];

const FOR_CANDIDATE = [
  'Проходите опрос и тест на свой грейд.',
  'Получаете категорию, которую видят работодатели.',
  'Видите зарплату до начала разговора.',
  'Решаете сами, кому открыть контакты.',
];

const FOR_EMPLOYER = [
  'Описываете, кого ищете: стек, специализацию, грейд.',
  'Получаете подборку с объяснением, почему кандидат подходит.',
  'Ищете по банку кандидатов с фильтрами и достижениями ФСП.',
  'Отправляете предложение с зарплатой от–до.',
];

function Scoreboard() {
  return (
    <div className="rounded-lg border border-ink bg-white shadow-hard">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-t-lg bg-ink px-4 py-3 text-sm text-white">
        <span className="font-bold">Backend · Middle</span>
        <span className="text-white/75">128 кандидатов · пример подборки</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[480px] text-left text-sm">
          <caption className="sr-only">Пример рейтинга кандидатов внутри категории</caption>
          <thead className="text-xs text-ink/70">
            <tr className="border-b border-muted">
              <th scope="col" className="px-4 py-2.5 font-normal">№</th>
              <th scope="col" className="px-4 py-2.5 font-normal">Кандидат</th>
              <th scope="col" className="px-4 py-2.5 font-normal">Тест, балл</th>
              <th scope="col" className="px-4 py-2.5 font-normal">ФСП</th>
              <th scope="col" className="px-4 py-2.5 text-right font-normal">Совпадение</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row, index) => {
              const top = index === 0;
              return (
                <tr
                  key={row.id}
                  className={top ? 'bg-brand text-white' : 'border-b border-muted last:border-0'}
                >
                  <td className="px-4 py-3 font-bold">{row.rank}</td>
                  <td className="px-4 py-3">Кандидат {row.id}</td>
                  <td className="px-4 py-3">{row.test}</td>
                  <td className="px-4 py-3">
                    {row.fsp ?? (
                      <span className="rounded border border-dashed border-muted px-1.5 py-0.5 text-xs text-ink/70">
                        нет истории
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-bold">{row.score}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="border-t border-ink px-4 py-4 motion-safe:animate-reveal">
        <p className="text-xs text-ink/70">Предложение кандидату 4812</p>
        <div className="mt-1.5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="font-bold">Senior Backend-разработчик</p>
            <p className="mt-0.5 text-sm text-ink/80">300 000 – 380 000 ₽ · удалённо</p>
          </div>
          <span className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-white">
            Отправить предложение
          </span>
        </div>
        <p className="mt-3 text-xs text-ink/70">
          Контакты кандидата откроются, когда он примет предложение.
        </p>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-5">
        <Logo />
        <nav className="hidden items-center gap-8 text-sm md:flex" aria-label="Разделы страницы">
          <a href="#how" className="hover:text-brand">Как это устроено</a>
          <a href="#audience" className="hover:text-brand">Кому подходит</a>
          <a href="#fsp" className="hover:text-brand">Достижения ФСП</a>
        </nav>
        <div className="flex items-center gap-3 text-sm">
          <Link href="/login" className="font-semibold hover:text-brand">
            Войти
          </Link>
          <Link
            href="/register"
            className="rounded-md bg-ink px-4 py-2 font-semibold text-white transition hover:bg-brand"
          >
            Регистрация
          </Link>
        </div>
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl grid-cols-1 gap-14 px-5 pb-20 pt-10 lg:grid-cols-[5fr_7fr] lg:items-center lg:pt-16">
          <div>
            <h1 className="text-4xl font-bold leading-[1.1] tracking-tight sm:text-5xl">
              Не откликайтесь вслепую. Вас найдут сами.
            </h1>
            <p className="mt-6 max-w-md text-base leading-relaxed text-ink/80">
              Категорию определяют тест и достижения Федерации спортивного программирования, а не
              резюме. Работодатель выбирает из рейтинга и сразу пишет, сколько готов платить.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/register?role=candidate"
                className="rounded-md bg-brand px-6 py-3.5 text-center text-sm font-semibold text-white transition hover:bg-brand-dark"
              >
                Я ищу работу
              </Link>
              <Link
                href="/register?role=employer"
                className="rounded-md border border-ink px-6 py-3.5 text-center text-sm font-semibold transition hover:bg-white"
              >
                Я работодатель
              </Link>
            </div>
          </div>

          <Scoreboard />
        </section>

        <section id="how" className="scroll-mt-4 border-y border-ink bg-white">
          <div className="mx-auto grid max-w-6xl grid-cols-1 gap-10 px-5 py-16 lg:grid-cols-[4fr_8fr]">
            <h2 className="text-2xl font-bold sm:text-3xl">Как это устроено</h2>
            <ol className="divide-y divide-muted">
              {STEPS.map((step, index) => (
                <li
                  key={step.title}
                  className="grid grid-cols-[2.5rem_1fr] gap-4 py-6 first:pt-0 last:pb-0"
                >
                  <span className="text-2xl font-bold text-brand">{index + 1}</span>
                  <div>
                    <h3 className="font-bold">{step.title}</h3>
                    <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-ink/75">{step.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="audience" className="mx-auto grid max-w-6xl scroll-mt-4 grid-cols-1 gap-6 px-5 py-16 lg:grid-cols-2">
          <div className="rounded-lg border border-muted bg-white p-8">
            <h2 className="text-2xl font-bold">Кандидату</h2>
            <ul className="mt-6 space-y-3 text-sm leading-relaxed">
              {FOR_CANDIDATE.map((item) => (
                <li key={item} className="flex gap-3">
                  <span className="mt-1.5 h-2 w-2 shrink-0 bg-brand" aria-hidden="true" />
                  {item}
                </li>
              ))}
            </ul>
            <Link
              href="/register?role=candidate"
              className="mt-8 inline-block rounded-md bg-brand px-6 py-3 text-sm font-semibold text-white transition hover:bg-brand-dark"
            >
              Я ищу работу
            </Link>
          </div>

          <div className="rounded-lg bg-ink p-8 text-white">
            <h2 className="text-2xl font-bold">Работодателю</h2>
            <ul className="mt-6 space-y-3 text-sm leading-relaxed">
              {FOR_EMPLOYER.map((item) => (
                <li key={item} className="flex gap-3">
                  <span className="mt-1.5 h-2 w-2 shrink-0 bg-accent" aria-hidden="true" />
                  {item}
                </li>
              ))}
            </ul>
            <Link
              href="/register?role=employer"
              className="mt-8 inline-block rounded-md bg-white px-6 py-3 text-sm font-semibold text-ink transition hover:bg-surface"
            >
              Я работодатель
            </Link>
          </div>
        </section>

        <section id="fsp" className="scroll-mt-4 border-t border-ink bg-white">
          <div className="mx-auto grid max-w-6xl grid-cols-1 gap-10 px-5 py-16 lg:grid-cols-2 lg:items-center">
            <div>
              <h2 className="text-2xl font-bold sm:text-3xl">Навыки подтверждены делом</h2>
              <p className="mt-5 max-w-lg text-base leading-relaxed text-ink/80">
                Результаты соревнований и мероприятий Федерации спортивного программирования
                попадают в профиль и поднимают кандидата выше в его категории.
              </p>
              <p className="mt-4 max-w-lg text-base leading-relaxed text-ink/80">
                Истории ФСП нет — это не помеха: категорию определяет тест, а достижения только
                усиливают профиль.
              </p>
            </div>

            <div className="on-brand overflow-hidden rounded-lg bg-brand p-6 text-white sm:p-8">
              {/* Сеть вынесена в верхнюю полосу панели, чтобы линии не проходили по тексту. */}
              <div className="relative -mx-6 -mt-6 mb-4 h-40 sm:-mx-8 sm:-mt-8">
                <NetworkArt className="pointer-events-none absolute inset-0 h-full w-full" />
              </div>
              <div>
                <p className="text-xs text-white/85">Пример профиля</p>
                <dl className="mt-3 divide-y divide-white/30 text-sm">
                  <div className="flex justify-between gap-4 py-3">
                    <dt>Тест на грейд</dt>
                    <dd className="font-bold">Middle подтверждён</dd>
                  </div>
                  <div className="flex justify-between gap-4 py-3">
                    <dt>Соревнования ФСП</dt>
                    <dd className="font-bold">3 участия</dd>
                  </div>
                  <div className="flex justify-between gap-4 py-3">
                    <dt>Профиль без истории ФСП</dt>
                    <dd className="font-bold">категория по тесту</dd>
                  </div>
                </dl>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-ink text-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-8 sm:flex-row sm:items-center sm:justify-between">
          <Logo light />
          <p className="text-xs text-white/80">
            Федерация спортивного программирования России ·{' '}
            <a
              href="https://fsp-russia.ru"
              target="_blank"
              rel="noreferrer"
              className="underline hover:text-white"
            >
              fsp-russia.ru
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
