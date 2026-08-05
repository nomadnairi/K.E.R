import { Container } from '@ker/ui';
import { Link } from 'react-router-dom';

import { LINKS } from '../config/links';
import { useHref, useT } from '../i18n';
import { Logo } from './Logo';

export function Footer() {
  const t = useT();
  const href = useHref();

  const columns = [
    {
      title: t.footer.product,
      links: [
        { label: t.nav.features, to: href('/features') },
        { label: t.nav.pricing, to: href('/pricing') },
        { label: t.nav.download, to: href('/download') },
        { label: t.nav.security, to: href('/security') },
      ],
    },
    {
      title: t.footer.resources,
      links: [
        { label: t.nav.docs, to: href('/docs') },
        { label: t.footer.roadmap, to: href('/roadmap') },
        { label: t.footer.changelog, to: href('/changelog') },
      ],
    },
  ];

  const external = [
    { label: t.footer.github, url: LINKS.github },
    { label: t.footer.telegram, url: LINKS.telegramBot },
    { label: t.footer.license, url: LINKS.license },
  ];

  return (
    <footer className="border-t border-border bg-base">
      <Container>
        <div className="grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <Logo />
            <p className="mt-3 text-sm text-text-muted">{t.footer.tagline}</p>
          </div>

          {columns.map((col) => (
            <div key={col.title}>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                {col.title}
              </h3>
              <ul className="mt-4 space-y-2.5">
                {col.links.map((l) => (
                  <li key={l.to}>
                    <Link
                      to={l.to}
                      className="text-sm text-text-body transition-colors hover:text-accent"
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              {t.footer.community}
            </h3>
            <ul className="mt-4 space-y-2.5">
              {external.map((l) => (
                <li key={l.label}>
                  <a
                    href={l.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-text-body transition-colors hover:text-accent"
                  >
                    {l.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="flex flex-col gap-2 border-t border-border py-6 text-xs
                        text-text-muted sm:flex-row sm:items-center sm:justify-between">
          <span>© {new Date().getFullYear()} K.E.R.</span>
          <span>{t.footer.rights}</span>
        </div>
      </Container>
    </footer>
  );
}
