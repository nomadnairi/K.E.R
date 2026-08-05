import { Badge, ButtonLink, Card, Container, Section } from '@ker/ui';

import { PageHeader } from '../components/PageHeader';
import { LINKS } from '../config/links';
import { formatSize, useRelease } from '../hooks/useRelease';
import { useT } from '../i18n';

/**
 * Purpose: get the app onto the visitor's machine.
 *
 * Windows is the only platform with a real build, so it is the only one
 * offered as a download; Linux and Android say what actually exists instead
 * of promising a date.
 */
export function DownloadPage() {
  const t = useT();
  const { release, loading, failed } = useRelease();

  return (
    <>
      <PageHeader title={t.download.title} subtitle={t.download.subtitle} />

      <Section>
        <div className="mx-auto max-w-2xl space-y-4">
          <Card className="p-7">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-h3 font-bold text-text">
                  {t.download.windows}
                </h2>
                <p className="mt-1 text-sm text-text-muted">
                  {t.download.installer} · {t.download.requirements}
                </p>
              </div>
              <Badge tone="accent">Windows</Badge>
            </div>

            {loading && (
              <p className="mt-6 text-sm text-text-muted">
                {t.download.loading}
              </p>
            )}

            {failed && (
              <div className="mt-6">
                <p className="text-sm text-text-muted">{t.download.failed}</p>
                <ButtonLink
                  href={LINKS.releases}
                  target="_blank"
                  rel="noreferrer"
                  size="lg"
                  className="mt-4"
                >
                  {t.download.download}
                </ButtonLink>
              </div>
            )}

            {release && (
              <>
                <dl className="mt-6 flex flex-wrap gap-x-8 gap-y-3 font-mono text-sm">
                  <div>
                    <dt className="text-text-muted">{t.download.version}</dt>
                    <dd className="text-text">{release.version || '—'}</dd>
                  </div>
                  {release.windows && (
                    <div>
                      <dt className="text-text-muted">{t.download.size}</dt>
                      <dd className="text-text">
                        {formatSize(release.windows.size)}
                      </dd>
                    </div>
                  )}
                </dl>

                <div className="mt-7 flex flex-wrap gap-3">
                  <ButtonLink
                    href={release.windows?.url ?? LINKS.releases}
                    size="lg"
                  >
                    {t.download.download}
                    {release.windows ? ' .exe' : ''}
                  </ButtonLink>
                  <ButtonLink
                    href={release.notesUrl}
                    target="_blank"
                    rel="noreferrer"
                    variant="secondary"
                    size="lg"
                  >
                    {t.download.releaseNotes}
                  </ButtonLink>
                </div>
              </>
            )}
          </Card>

          {/* Honest status for everything else. */}
          <Card className="p-7">
            <h2 className="text-body font-semibold text-text">
              {t.download.otherPlatforms}
            </h2>
            <ul className="mt-4 space-y-3">
              <li className="flex items-center justify-between gap-4">
                <span className="text-sm text-text-body">
                  Linux
                  <span className="ml-2 text-text-muted">
                    — {t.download.linuxNote}
                  </span>
                </span>
                <Badge tone="soon">{t.common.soon}</Badge>
              </li>
              <li className="flex items-center justify-between gap-4">
                <span className="text-sm text-text-body">
                  Android
                  <span className="ml-2 text-text-muted">
                    — {t.download.androidNote}
                  </span>
                </span>
                <Badge tone="soon">{t.common.soon}</Badge>
              </li>
            </ul>
          </Card>

          <Card interactive className="p-7">
            <a
              href={LINKS.github}
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-between gap-4"
            >
              <span>
                <span className="block text-body font-semibold text-text">
                  {t.download.sourceCode}
                </span>
                <span className="mt-1 block text-sm text-text-muted">
                  {t.download.sourceCaption}
                </span>
              </span>
              <span className="text-accent">→</span>
            </a>
          </Card>
        </div>
      </Section>

      <Container>
        <p className="pb-16 text-center text-xs text-text-muted">
          {t.download.checksum}
        </p>
      </Container>
    </>
  );
}
