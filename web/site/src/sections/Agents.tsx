import { Card, Reveal, Section } from '@ker/ui';

import { useT } from '../i18n';

/** Four steps, shown as a chain — what "delegates to sub-agents" means. */
export function Agents() {
  const t = useT();

  return (
    <Section id="agents" title={t.agents.title} subtitle={t.agents.subtitle}>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {t.agents.steps.map((step, i) => (
          <Reveal key={step.name} delay={i * 0.07} className="h-full">
            <Card className="relative h-full p-6">
              <span className="font-mono text-sm text-accent">
                {String(i + 1).padStart(2, '0')}
              </span>
              <h3 className="mt-3 text-body font-semibold text-text">
                {step.name}
              </h3>
              <p className="mt-1.5 text-sm text-text-muted">{step.text}</p>

              {/* Connector into the next card — desktop only. */}
              {i < t.agents.steps.length - 1 && (
                <span
                  aria-hidden="true"
                  className="absolute right-[-10px] top-1/2 hidden h-px w-5
                             bg-border-strong lg:block"
                />
              )}
            </Card>
          </Reveal>
        ))}
      </div>

      <p className="mt-8 text-center text-sm text-text-muted">
        {t.agents.note}
      </p>
    </Section>
  );
}
