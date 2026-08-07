import { ButtonLink, Card, Container, Reveal } from '@ker/ui';

import { LINKS } from '../config/links';
import { useT } from '../i18n';

/** A mock of the Command Deck window — the product, not a stock illustration. */
function DeckPreview() {
  return (
    <Card glass className="overflow-hidden p-0">
      {/* Title bar */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-danger/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-warning/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-accent/70" />
        <span className="ml-2 font-mono text-xs text-text-muted">
          K.E.R. — Command Deck
        </span>
      </div>

      <div className="grid grid-cols-[auto_1fr]">
        {/* Icon rail */}
        <div className="flex flex-col gap-4 border-r border-border p-4">
          {[0, 1, 2, 3, 4].map((i) => (
            <span
              key={i}
              className={
                'h-5 w-5 rounded ' + (i === 0 ? 'bg-accent/70' : 'bg-raised')
              }
            />
          ))}
        </div>

        {/* Body */}
        <div className="space-y-3 p-5">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 animate-pulse-glow rounded-full bg-accent" />
            <span className="font-mono text-xs text-accent">online</span>
          </div>
          <div className="h-2 w-3/4 rounded bg-raised" />
          <div className="h-2 w-1/2 rounded bg-raised" />
          <div className="mt-5 grid grid-cols-3 gap-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-14 rounded border border-border bg-elevated" />
            ))}
          </div>
          <div className="mt-4 h-9 rounded-button border border-border bg-base" />
        </div>
      </div>
    </Card>
  );
}

export function Desktop() {
  const t = useT();

  return (
    <section id="desktop" className="py-20 sm:py-28">
      <Container>
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <Reveal className="order-2 lg:order-1">
            <DeckPreview />
          </Reveal>

          <Reveal delay={0.08} className="order-1 lg:order-2">
            <h2 className="text-h3 font-bold text-text sm:text-h2">
              {t.desktop.title}
            </h2>
            <p className="mt-3 text-body text-text-muted">
              {t.desktop.subtitle}
            </p>
            <ul className="mt-7 space-y-3">
              {t.desktop.points.map((point) => (
                <li
                  key={point}
                  className="flex gap-3 text-body text-text-body before:mt-2.5
                             before:h-1 before:w-1 before:shrink-0
                             before:rounded-full before:bg-accent"
                >
                  {point}
                </li>
              ))}
            </ul>
            <ButtonLink
              href={LINKS.releases}
              target="_blank"
              rel="noreferrer"
              variant="secondary"
              size="lg"
              className="mt-8"
            >
              {t.desktop.cta}
            </ButtonLink>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}
