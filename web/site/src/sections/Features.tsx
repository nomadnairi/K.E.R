import { Button, Card, Reveal, Section } from '@ker/ui';
import { useNavigate } from 'react-router-dom';

import { FeatureIcon, type FeatureKey } from '../components/FeatureIcon';
import { useHref, useT } from '../i18n';

/** The 3x3 grid from the mockup, in the mockup's order. */
const ORDER: readonly FeatureKey[] = [
  'memory',
  'agents',
  'actions',
  'automation',
  'integrations',
  'voice',
  'security',
  'multiplatform',
  'opensource',
] as const;

export function Features({
  showAll = true,
  showHeader = true,
}: {
  showAll?: boolean;
  /** Off when the page above already carries the same title. */
  showHeader?: boolean;
}) {
  const t = useT();
  const href = useHref();
  const navigate = useNavigate();

  return (
    <Section
      id="features"
      title={showHeader ? t.features.title : undefined}
      subtitle={showHeader ? t.features.subtitle : undefined}
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {ORDER.map((key, i) => {
          const item = t.features.items[key];
          return (
            <Reveal key={key} delay={(i % 3) * 0.06} className="h-full">
              <Card interactive className="h-full p-6">
                <FeatureIcon name={key} className="h-6 w-6 text-accent" />
                <h3 className="mt-4 text-body font-semibold text-text">
                  {item.name}
                </h3>
                <p className="mt-1.5 text-sm text-text-muted">{item.text}</p>
              </Card>
            </Reveal>
          );
        })}
      </div>

      {showAll && (
        <div className="mt-10 flex justify-center">
          <Button variant="secondary" onClick={() => navigate(href('/features'))}>
            {t.features.all} →
          </Button>
        </div>
      )}
    </Section>
  );
}
