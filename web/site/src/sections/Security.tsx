import { Card, Reveal, Section } from '@ker/ui';

import { useT } from '../i18n';

/**
 * Trust section, placed before pricing on the home page: the objection "will
 * it leak my data?" has to be answered before anyone looks at a price.
 *
 * Every claim here is checkable in the repository. The closing line says
 * outright that E2E is not shipped — `docs/SECURITY_ARCHITECTURE.md` marks it
 * as target architecture, and claiming it would be the one lie that discredits
 * the rest.
 */
export function Security({ showHeader = true }: { showHeader?: boolean }) {
  const t = useT();

  return (
    <Section
      id="security"
      title={showHeader ? t.security.title : undefined}
      subtitle={showHeader ? t.security.subtitle : undefined}
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {t.security.items.map((item, i) => (
          <Reveal key={item.name} delay={(i % 3) * 0.06} className="h-full">
            <Card className="h-full p-6">
              <h3 className="text-body font-semibold text-text">{item.name}</h3>
              <p className="mt-1.5 text-sm text-text-muted">{item.text}</p>
            </Card>
          </Reveal>
        ))}
      </div>

      <p className="mt-8 text-center text-sm text-text-muted">
        {t.security.honest}
      </p>
    </Section>
  );
}
