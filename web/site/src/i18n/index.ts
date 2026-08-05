import { createContext, useContext } from 'react';

import { en } from './en';
import { type Dictionary, ru } from './ru';

export type Locale = 'ru' | 'en';

export const LOCALES: readonly Locale[] = ['ru', 'en'] as const;

const DICTIONARIES: Record<Locale, Dictionary> = { ru, en };

/** RU lives at `/`, EN at `/en/…` — both indexable, both linkable. */
export function localeFromPath(pathname: string): Locale {
  return pathname === '/en' || pathname.startsWith('/en/') ? 'en' : 'ru';
}

/** Strip the locale prefix, so routes are declared once and reused. */
export function stripLocale(pathname: string): string {
  if (pathname === '/en') return '/';
  if (pathname.startsWith('/en/')) return pathname.slice(3) || '/';
  return pathname || '/';
}

/** Build an href for `path` in `locale`. */
export function localizedPath(path: string, locale: Locale): string {
  const clean = path.startsWith('/') ? path : `/${path}`;
  if (locale === 'ru') return clean;
  return clean === '/' ? '/en/' : `/en${clean}`;
}

export const LocaleContext = createContext<Locale>('ru');

export function useLocale(): Locale {
  return useContext(LocaleContext);
}

/** The dictionary for the active locale. */
export function useT(): Dictionary {
  return DICTIONARIES[useLocale()];
}

/** Prefix a path with the active locale — for every internal link. */
export function useHref(): (path: string) => string {
  const locale = useLocale();
  return (path: string) => localizedPath(path, locale);
}

export type { Dictionary };
