import { Badge, Card, Reveal, Section } from '@ker/ui';

import { PageHeader } from '../components/PageHeader';
import { ROADMAP, type Status } from '../config/roadmap';
import { useLocale, useT } from '../i18n';

const TONE: Record<Status, 'accent' | 'neutral' | 'soon'> = {
  done: 'accent',
  partial: 'neutral',
  planned: 'soon',
};

/** Purpose: show honestly what exists and what does not. */
export function RoadmapPage() {
  const t = useT();
  const locale = useLocale();

  const label: Record<Status, string> = {
    done: t.roadmapPage.done,
    partial: t.roadmapPage.partial,
    planned: t.roadmapPage.planned,
  };

  return (
    <>
      <PageHeader title={t.roadmapPage.title} subtitle={t.roadmapPage.subtitle} />

      <Section>
        <div className="mx-auto max-w-3xl space-y-5">
          {ROADMAP.map((group, gi) => (
            <Reveal key={group.title} delay={gi * 0.05}>
              <Card className="p-7">
                <h2 className="text-body font-semibold text-text">
                  {locale === 'ru' ? group.title : group.titleEn}
                </h2>
                <ul className="mt-4 divide-y divide-border">
                  {group.items.map((item) => (
                    <li
                      key={item.name}
                      className="flex items-center justify-between gap-4 py-3"
                    >
                      <span className="text-sm text-text-body">
                        {locale === 'ru' ? item.name : item.nameEn}
                      </span>
                      <Badge tone={TONE[item.status]}>{label[item.status]}</Badge>
                    </li>
                  ))}
                </ul>
              </Card>
            </Reveal>
          ))}

          <p className="pt-2 text-center text-xs text-text-muted">
            {t.roadmapPage.source}
          </p>
        </div>
      </Section>
    </>
  );
}
