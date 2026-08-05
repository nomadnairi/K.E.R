import { Container } from '@ker/ui';

/** Shared masthead for the inner pages — one title, one line, no essay. */
export function PageHeader({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="relative overflow-hidden border-b border-border pb-14 pt-32">
      <div className="pointer-events-none absolute inset-0 bg-tech-grid opacity-50" />
      <Container className="relative">
        <h1 className="text-h2 font-bold text-text sm:text-h1">{title}</h1>
        {subtitle && (
          <p className="mt-3 text-lead text-text-muted">{subtitle}</p>
        )}
      </Container>
    </div>
  );
}
