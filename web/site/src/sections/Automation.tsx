import { Card, Reveal, Section } from '@ker/ui';

import { useT } from '../i18n';

export function Automation() {
  const t = useT();

  return (
    <Section
      id="automation"
      title={t.automation.title}
      subtitle={t.automation.subtitle}
    >
      <div className="grid gap-4 sm:grid-cols-3">
        {t.automation.items.map((item, i) => (
          <Reveal key={item.name} delay={i * 0.07} className="h-full">
            <Card className="h-full p-6">
              <h3 className="text-body font-semibold text-text">{item.name}</h3>
              <p className="mt-1.5 text-sm text-text-muted">{item.text}</p>
            </Card>
          </Reveal>
        ))}
      </div>

      {/* Stated plainly: proactive messages are opt-in. An assistant that
          messages first is only welcome if the user asked for it. */}
      <p className="mt-8 text-center text-sm text-text-muted">
        {t.automation.optIn}
      </p>
    </Section>
  );
}
