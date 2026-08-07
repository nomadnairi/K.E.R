import type { ReactNode } from 'react';

import { cn } from '../cn';

export function Container({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn('mx-auto w-full max-w-container px-5 sm:px-8', className)}>
      {children}
    </div>
  );
}

/**
 * A page section with its heading. The brief is strict about this shape:
 * title + one line + cards. No paragraphs, so there is no slot for one.
 */
export function Section({
  id,
  title,
  subtitle,
  align = 'center',
  className,
  children,
}: {
  id?: string;
  title?: string;
  subtitle?: string;
  align?: 'center' | 'left';
  className?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className={cn('py-20 sm:py-28', className)}>
      <Container>
        {(title || subtitle) && (
          <header
            className={cn(
              'mb-12 sm:mb-16',
              align === 'center' && 'text-center',
            )}
          >
            {title && (
              <h2 className="text-h3 font-bold text-text sm:text-h2">{title}</h2>
            )}
            {subtitle && (
              <p
                className={cn(
                  'mt-3 text-body text-text-muted',
                  align === 'center' && 'mx-auto',
                )}
              >
                {subtitle}
              </p>
            )}
          </header>
        )}
        {children}
      </Container>
    </section>
  );
}
