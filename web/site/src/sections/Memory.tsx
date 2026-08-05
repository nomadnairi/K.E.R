import { Card, Container, Reveal } from '@ker/ui';

import { useT } from '../i18n';

function Check() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="mt-0.5 h-4 w-4 shrink-0 text-accent"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m5 13 4 4L19 7" />
    </svg>
  );
}

/**
 * Memory is the hardest thing to explain in prose and the easiest to show, so
 * the right-hand column is a two-turn transcript a week apart rather than a
 * paragraph about "semantic recall".
 */
export function Memory() {
  const t = useT();

  return (
    <section id="memory" className="py-20 sm:py-28">
      <Container>
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <Reveal>
            <h2 className="text-h3 font-bold text-text sm:text-h2">
              {t.memory.title}
            </h2>
            <p className="mt-3 text-body text-text-muted">{t.memory.subtitle}</p>
            <ul className="mt-7 space-y-3">
              {t.memory.points.map((point) => (
                <li key={point} className="flex gap-3 text-body text-text-body">
                  <Check />
                  {point}
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal delay={0.1}>
            <Card className="p-6">
              <div className="space-y-3">
                <Bubble side="user">{t.memory.demoUser}</Bubble>

                <div className="flex items-center gap-3 py-1">
                  <span className="h-px flex-1 bg-border" />
                  <span className="text-xs text-text-muted">
                    {t.memory.demoLater}
                  </span>
                  <span className="h-px flex-1 bg-border" />
                </div>

                <Bubble side="user">{t.memory.demoAsk}</Bubble>
                <Bubble side="assistant">{t.memory.demoAnswer}</Bubble>
              </div>
            </Card>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}

function Bubble({
  side,
  children,
}: {
  side: 'user' | 'assistant';
  children: string;
}) {
  const isUser = side === 'user';
  return (
    <div className={isUser ? 'flex justify-end' : 'flex justify-start'}>
      <p
        className={
          'max-w-[85%] rounded-card px-4 py-2.5 text-sm ' +
          (isUser
            ? 'bg-raised text-text-body'
            : 'border border-accent/30 bg-accent/10 text-text')
        }
      >
        {children}
      </p>
    </div>
  );
}
