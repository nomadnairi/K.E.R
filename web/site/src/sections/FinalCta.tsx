import { ButtonLink, Container, Reveal } from '@ker/ui';

import { LINKS } from '../config/links';
import { useT } from '../i18n';

export function FinalCta() {
  const t = useT();

  return (
    <section className="relative overflow-hidden py-24 sm:py-32">
      <div className="pointer-events-none absolute inset-0 bg-tech-grid opacity-60" />
      <Container className="relative">
        <Reveal className="text-center">
          <h2 className="text-h3 font-bold text-text sm:text-h2">
            {t.hero.tagline}
          </h2>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <ButtonLink
              href={LINKS.telegramBot}
              target="_blank"
              rel="noreferrer"
              size="lg"
            >
              {t.hero.ctaPrimary}
            </ButtonLink>
            <ButtonLink
              href={LINKS.releases}
              target="_blank"
              rel="noreferrer"
              variant="secondary"
              size="lg"
            >
              {t.hero.ctaSecondary}
            </ButtonLink>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
