import { ButtonLink, Container } from '@ker/ui';
import { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';

import { LINKS } from '../config/links';
import { localizedPath, stripLocale, useHref, useLocale, useT } from '../i18n';
import { Logo } from './Logo';

export function Nav() {
  const t = useT();
  const href = useHref();
  const locale = useLocale();
  const { pathname } = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  // Close the mobile sheet on navigation — otherwise it covers the page the
  // user just asked for.
  useEffect(() => setOpen(false), [pathname]);

  // Transparent over the hero, frosted once the page moves — the glass only
  // appears where it has something to sit on top of.
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const items = [
    { to: '/features', label: t.nav.features },
    { to: '/pricing', label: t.nav.pricing },
    { to: '/download', label: t.nav.download },
    { to: '/docs', label: t.nav.docs },
    { to: '/security', label: t.nav.security },
  ];

  const other = locale === 'ru' ? 'en' : 'ru';

  return (
    <header
      className={
        'fixed inset-x-0 top-0 z-50 transition-colors duration-300 ' +
        (scrolled
          ? 'border-b border-border bg-base/70 backdrop-blur-xl'
          : 'border-b border-transparent')
      }
    >
      <Container>
        <nav className="flex h-16 items-center gap-8">
          <Link to={href('/')} aria-label="K.E.R.">
            <Logo />
          </Link>

          <ul className="hidden items-center gap-7 md:flex">
            {items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={href(item.to)}
                  className={({ isActive }) =>
                    'text-sm transition-colors ' +
                    (isActive
                      ? 'text-accent'
                      : 'text-text-body hover:text-text')
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>

          <div className="ml-auto flex items-center gap-3">
            <Link
              to={localizedPath(stripLocale(pathname), other)}
              className="rounded-button px-2 py-1 text-sm font-medium uppercase
                         text-text-muted transition-colors hover:text-text"
              hrefLang={other}
            >
              {other}
            </Link>
            <ButtonLink
              href={LINKS.telegramBot}
              target="_blank"
              rel="noreferrer"
              size="md"
            >
              {t.nav.start}
            </ButtonLink>

            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              aria-label="Menu"
              className="-mr-2 flex h-10 w-10 items-center justify-center
                         rounded-button text-text-body md:hidden"
            >
              <svg
                viewBox="0 0 24 24"
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinecap="round"
                aria-hidden="true"
              >
                {open ? (
                  <path d="M6 6l12 12M18 6L6 18" />
                ) : (
                  <path d="M4 7h16M4 12h16M4 17h16" />
                )}
              </svg>
            </button>
          </div>
        </nav>
      </Container>

      {open && (
        <div className="border-t border-border bg-base/95 backdrop-blur-xl md:hidden">
          <Container>
            <ul className="flex flex-col py-2">
              {items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={href(item.to)}
                    className={({ isActive }) =>
                      'block py-3 text-body transition-colors ' +
                      (isActive ? 'text-accent' : 'text-text-body')
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </Container>
        </div>
      )}
    </header>
  );
}
