import { Badge, ButtonLink, Card, Reveal, Section, cn } from '@ker/ui';

import { LINKS } from '../config/links';
import { PLANS, type Plan } from '../config/plans';
import { useLocale, useT } from '../i18n';
import { plural } from '../i18n/plural';

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
 * Cards only, per the brief — no comparison essay.
 *
 * Every limit comes from `src/config/plans.ts`, which mirrors
 * `jarvis/billing/plans.py`. The site must never quote a price the bot will
 * not actually charge.
 */
export function Pricing({ showHeader = true }: { showHeader?: boolean }) {
  const t = useT();
  const locale = useLocale();

  const featuresFor = (plan: Plan): string[] => {
    const p = t.pricing.perks;
    const l = t.pricing.limits;

    const messages =
      plan.dailyMessages === null
        ? l.messagesUnlimited
        : `${plan.dailyMessages} ${l.messages}`;
    const integrations =
      plan.integrations === null
        ? l.integrationsUnlimited
        : `${plan.integrations} ${plural(locale, plan.integrations, l.integrations)}`;

    if (plan.id === 'free') return [messages, integrations, p.memory];
    if (plan.id === 'plus')
      return [messages, integrations, p.memory, p.allModels, p.images, p.desktop];
    return [
      messages,
      integrations,
      p.memory,
      p.allModels,
      p.images,
      p.desktop,
      p.api,
      p.priority,
    ];
  };

  return (
    <Section
      id="pricing"
      title={showHeader ? t.pricing.title : undefined}
      subtitle={showHeader ? t.pricing.subtitle : undefined}
    >
      <div className="grid items-start gap-5 lg:grid-cols-3">
        {PLANS.map((plan, i) => {
          const tier = t.pricing.tiers[plan.id];
          return (
            <Reveal key={plan.id} delay={i * 0.07} className="h-full">
              <Card
                className={cn(
                  'relative flex h-full flex-col p-7',
                  plan.featured && 'border-accent/50 shadow-glow',
                )}
              >
                {plan.featured && (
                  <span className="absolute right-6 top-6">
                    <Badge tone="accent">{t.pricing.popular}</Badge>
                  </span>
                )}

                <h3 className="text-h3 font-bold text-text">{tier.name}</h3>
                <p className="mt-1 text-sm text-text-muted">{tier.caption}</p>

                <p className="mt-6 flex items-baseline gap-2">
                  {plan.priceStars === 0 ? (
                    <span className="text-h2 font-bold text-text">
                      {t.pricing.free}
                    </span>
                  ) : (
                    <>
                      <span className="text-h2 font-bold text-text">
                        {plan.priceStars.toLocaleString('ru-RU')}
                      </span>
                      <span className="text-body text-text-muted">
                        {t.pricing.stars} / {t.pricing.perMonth}
                      </span>
                    </>
                  )}
                </p>

                <ul className="mt-7 flex-1 space-y-3">
                  {featuresFor(plan).map((f) => (
                    <li key={f} className="flex gap-3 text-sm text-text-body">
                      <Check />
                      {f}
                    </li>
                  ))}
                </ul>

                <ButtonLink
                  href={LINKS.telegramBot}
                  target="_blank"
                  rel="noreferrer"
                  variant={plan.featured ? 'primary' : 'secondary'}
                  size="lg"
                  className="mt-8 w-full"
                >
                  {plan.priceStars === 0
                    ? t.pricing.cta.free
                    : `${t.pricing.cta.paid} ${tier.name}`}
                </ButtonLink>
              </Card>
            </Reveal>
          );
        })}
      </div>

      <p className="mt-8 text-center text-sm text-text-muted">
        {t.pricing.note}
      </p>
    </Section>
  );
}
