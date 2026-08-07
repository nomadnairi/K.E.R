import { Card, Section } from '@ker/ui';
import { useState } from 'react';

import { useT } from '../i18n';

export function Faq() {
  const t = useT();
  const [open, setOpen] = useState<number | null>(0);

  return (
    <Section id="faq" title={t.faq.title}>
      <div className="mx-auto max-w-2xl space-y-3">
        {t.faq.items.map((item, i) => {
          const isOpen = open === i;
          return (
            <Card key={item.q} className="overflow-hidden">
              <h3>
                <button
                  type="button"
                  onClick={() => setOpen(isOpen ? null : i)}
                  aria-expanded={isOpen}
                  className="flex w-full items-center justify-between gap-4 px-6
                             py-5 text-left"
                >
                  <span className="text-body font-medium text-text">
                    {item.q}
                  </span>
                  <svg
                    viewBox="0 0 24 24"
                    className={
                      'h-5 w-5 shrink-0 text-text-muted transition-transform ' +
                      (isOpen ? 'rotate-45' : '')
                    }
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    strokeLinecap="round"
                    aria-hidden="true"
                  >
                    <path d="M12 5v14M5 12h14" />
                  </svg>
                </button>
              </h3>
              {isOpen && (
                <p className="px-6 pb-5 text-body text-text-muted">{item.a}</p>
              )}
            </Card>
          );
        })}
      </div>
    </Section>
  );
}
