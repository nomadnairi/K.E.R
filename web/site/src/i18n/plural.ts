import type { Locale } from './index';

/**
 * Russian needs three plural forms (1 интеграция / 2 интеграции /
 * 5 интеграций); English needs two. Getting this wrong is small but it is
 * exactly the kind of detail that makes a page read as machine-made.
 */
export function plural(
  locale: Locale,
  n: number,
  forms: readonly [string, string, string],
): string {
  if (locale !== 'ru') return n === 1 ? forms[0] : forms[1];

  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1];
  return forms[2];
}
