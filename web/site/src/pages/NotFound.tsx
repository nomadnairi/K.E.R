import { ButtonLink, Container } from '@ker/ui';

import { useHref, useLocale } from '../i18n';

export function NotFound() {
  const href = useHref();
  const locale = useLocale();

  return (
    <Container className="flex min-h-[70vh] flex-col items-center justify-center
                          text-center">
      <p className="font-mono text-h2 font-bold text-accent">404</p>
      <p className="mt-3 text-body text-text-muted">
        {locale === 'ru' ? 'Такой страницы нет.' : 'No such page.'}
      </p>
      <ButtonLink href={href('/')} variant="secondary" className="mt-7">
        {locale === 'ru' ? 'На главную' : 'Back home'}
      </ButtonLink>
    </Container>
  );
}
