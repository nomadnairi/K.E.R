import type { ReactNode } from 'react';

import { cn } from '../cn';

type Tone = 'accent' | 'neutral' | 'soon';

const TONES: Record<Tone, string> = {
  accent: 'bg-accent/12 text-accent border-accent/30',
  neutral: 'bg-raised text-text-body border-border',
  /** For "Скоро" — visibly future, never mistaken for shipped. */
  soon: 'bg-raised text-text-muted border-border',
};

export function Badge({
  tone = 'neutral',
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-pill border px-2.5 py-0.5 ' +
          'text-xs font-medium',
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** A capability chip — the row under the hero headline. */
export function Pill({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return (
    <span
      className="inline-flex items-center gap-2 rounded-pill border border-border
                 bg-elevated/60 px-3.5 py-2 text-sm text-text-body backdrop-blur-sm"
    >
      {icon ? <span className="text-accent">{icon}</span> : null}
      {children}
    </span>
  );
}
