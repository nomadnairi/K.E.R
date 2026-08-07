import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '../cn';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Lift the border and add a halo on hover — for cards that are links. */
  interactive?: boolean;
  /** Frosted panel instead of a solid one (nav, modals, floating widgets). */
  glass?: boolean;
  children: ReactNode;
}

export function Card({
  interactive = false,
  glass = false,
  className,
  children,
  ...rest
}: CardProps) {
  return (
    <div
      className={cn(
        'rounded-card border border-border',
        glass ? 'bg-elevated/60 backdrop-blur-xl' : 'bg-elevated',
        interactive &&
          'transition-all duration-200 hover:border-border-strong ' +
            'hover:shadow-glow-lg hover:-translate-y-0.5',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
