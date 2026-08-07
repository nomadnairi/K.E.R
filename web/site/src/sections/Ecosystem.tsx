import { Badge, Card, Reveal, Section } from '@ker/ui';

import { LogoMark } from '../components/Logo';
import { useT } from '../i18n';

/**
 * The section that makes the positioning legible: K.E.R. is the core, and
 * Telegram / Desktop / Web are clients of it. Without this the whole site
 * reads as "a Telegram bot with a landing page".
 */
export function Ecosystem() {
  const t = useT();

  const clients = [
    { key: 'telegram', ...t.ecosystem.clients.telegram, soon: false },
    { key: 'desktop', ...t.ecosystem.clients.desktop, soon: false },
    { key: 'web', ...t.ecosystem.clients.web, soon: true },
  ];

  return (
    <Section
      id="ecosystem"
      title={t.ecosystem.title}
      subtitle={t.ecosystem.subtitle}
    >
      <div className="mx-auto max-w-3xl">
        {/* The core */}
        <Reveal>
          <Card className="mx-auto flex max-w-sm flex-col items-center gap-2 p-7 text-center">
            <LogoMark className="h-9 w-9 text-accent" />
            <p className="text-sm font-bold tracking-[0.16em] text-text">
              {t.ecosystem.core}
            </p>
            <p className="text-sm text-text-muted">{t.ecosystem.coreCaption}</p>
          </Card>
        </Reveal>

        {/* Connector: one core branching into three clients. */}
        <div aria-hidden="true" className="flex justify-center">
          <svg viewBox="0 0 600 64" className="h-16 w-full max-w-2xl">
            <path
              d="M300 0 v22 M100 64 v-20 a10 10 0 0 1 10-10 h380 a10 10 0 0 1 10 10 v20 M300 32 v32"
              fill="none"
              stroke="#2A3D26"
              strokeWidth="1.5"
            />
          </svg>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          {clients.map((client, i) => (
            <Reveal key={client.key} delay={i * 0.07} className="h-full">
              <Card className="flex h-full flex-col gap-1.5 p-5 text-center">
                <div className="flex items-center justify-center gap-2">
                  <span className="text-body font-semibold text-text">
                    {client.name}
                  </span>
                  {client.soon && (
                    <Badge tone="soon">{t.ecosystem.soon}</Badge>
                  )}
                </div>
                <p className="text-sm text-text-muted">{client.caption}</p>
              </Card>
            </Reveal>
          ))}
        </div>
      </div>
    </Section>
  );
}
