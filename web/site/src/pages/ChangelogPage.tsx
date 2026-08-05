import { ButtonLink, Card, Section } from '@ker/ui';
import { useEffect, useState } from 'react';

import { PageHeader } from '../components/PageHeader';
import { LINKS } from '../config/links';
import { useLocale, useT } from '../i18n';

interface Entry {
  version: string;
  date: string;
  url: string;
  body: string;
}

/**
 * Purpose: show what changed, release by release.
 *
 * Sourced from the GitHub Releases API — there is no CHANGELOG.md in the
 * repository, and inventing a version history would be exactly the kind of
 * unverifiable content the brief rules out.
 */
export function ChangelogPage() {
  const t = useT();
  const locale = useLocale();
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch(`https://api.github.com/repos/nomadnairi/K.E.R/releases?per_page=20`, {
      headers: { Accept: 'application/vnd.github+json' },
    })
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((data: Array<Record<string, string>>) => {
        if (!alive) return;
        setEntries(
          data.map((r) => ({
            version: (r.tag_name ?? '').replace(/^v/, ''),
            date: r.published_at ?? '',
            url: r.html_url ?? LINKS.releases,
            body: r.body ?? '',
          })),
        );
      })
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, []);

  const fmt = (iso: string) =>
    iso
      ? new Date(iso).toLocaleDateString(locale === 'ru' ? 'ru-RU' : 'en-GB', {
          year: 'numeric',
          month: 'long',
          day: 'numeric',
        })
      : '';

  return (
    <>
      <PageHeader
        title={t.changelogPage.title}
        subtitle={t.changelogPage.subtitle}
      />

      <Section>
        <div className="mx-auto max-w-2xl space-y-4">
          {!entries && !failed && (
            <p className="text-sm text-text-muted">{t.changelogPage.loading}</p>
          )}

          {failed && (
            <Card className="p-7">
              <p className="text-sm text-text-muted">{t.changelogPage.failed}</p>
              <ButtonLink
                href={LINKS.releases}
                target="_blank"
                rel="noreferrer"
                variant="secondary"
                className="mt-4"
              >
                {t.changelogPage.viewOnGithub}
              </ButtonLink>
            </Card>
          )}

          {entries?.map((e) => (
            <Card key={e.version + e.date} className="p-7">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 className="font-mono text-h3 font-bold text-accent">
                  {e.version}
                </h2>
                <time className="text-sm text-text-muted">{fmt(e.date)}</time>
              </div>
              {e.body && (
                <p className="mt-4 whitespace-pre-line text-sm text-text-body">
                  {e.body.slice(0, 600)}
                  {e.body.length > 600 ? '…' : ''}
                </p>
              )}
              <a
                href={e.url}
                target="_blank"
                rel="noreferrer"
                className="mt-4 inline-block text-sm text-accent hover:underline"
              >
                {t.changelogPage.viewOnGithub} →
              </a>
            </Card>
          ))}

          {entries?.length === 0 && (
            <Card className="p-7">
              <p className="text-sm text-text-muted">{t.changelogPage.failed}</p>
            </Card>
          )}
        </div>
      </Section>
    </>
  );
}
