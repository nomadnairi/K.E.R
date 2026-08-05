import { Card, Container, cn } from '@ker/ui';
import { useMemo, useState } from 'react';

import { ALL_ARTICLES, DOCS, type DocArticle, type DocBlock } from '../content/docs';
import { useLocale, useT } from '../i18n';

function pick<T extends string | string[]>(
  locale: 'ru' | 'en',
  block: { ru: T; en: T },
): T {
  return locale === 'ru' ? block.ru : block.en;
}

function Block({ block }: { block: DocBlock }) {
  const locale = useLocale();
  const value = pick(locale, block);

  if (block.kind === 'steps') {
    return (
      <ol className="my-5 space-y-3">
        {(value as string[]).map((step, i) => (
          <li key={step} className="flex gap-3.5">
            <span
              className="flex h-6 w-6 shrink-0 items-center justify-center
                         rounded-full border border-accent/40 font-mono text-xs
                         text-accent"
            >
              {i + 1}
            </span>
            <span className="text-body text-text-body">{step}</span>
          </li>
        ))}
      </ol>
    );
  }

  if (block.kind === 'note') {
    return (
      <p
        className="my-5 rounded-card border border-accent/25 bg-accent/[0.07]
                   px-4 py-3 text-sm text-text-body"
      >
        {value as string}
      </p>
    );
  }

  if (block.kind === 'code') {
    return (
      <pre
        className="my-5 overflow-x-auto rounded-card border border-border
                   bg-base p-4 font-mono text-xs text-text-body"
      >
        <code>{value as string}</code>
      </pre>
    );
  }

  return <p className="my-4 text-body text-text-body">{value as string}</p>;
}

/**
 * Purpose: teach someone to use the product.
 *
 * Left navigation, right article, client-side search — the search index is
 * just the article list, so there is no external service and no extra
 * request.
 */
export function DocsPage() {
  const t = useT();
  const locale = useLocale();
  const [slug, setSlug] = useState(ALL_ARTICLES[0]?.slug ?? '');
  const [query, setQuery] = useState('');

  const title = (a: DocArticle) => (locale === 'ru' ? a.titleRu : a.titleEn);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return null;
    return ALL_ARTICLES.filter((a) => {
      const haystack = [
        title(a),
        ...a.blocks.flatMap((b) => {
          const v = pick(locale, b);
          return Array.isArray(v) ? v : [v];
        }),
      ]
        .join(' ')
        .toLowerCase();
      return haystack.includes(q);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, locale]);

  const article = ALL_ARTICLES.find((a) => a.slug === slug) ?? ALL_ARTICLES[0];

  return (
    <div className="pt-24">
      <Container>
        <div className="grid gap-10 py-12 lg:grid-cols-[240px_1fr]">
          {/* Sidebar */}
          <aside className="lg:sticky lg:top-24 lg:self-start">
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t.docsPage.search}
              className="mb-6 w-full rounded-button border border-border
                         bg-elevated px-3.5 py-2.5 text-sm text-text
                         placeholder:text-text-muted focus:border-accent-dim"
            />

            {matches ? (
              <ul className="space-y-1">
                {matches.length === 0 && (
                  <li className="text-sm text-text-muted">
                    {t.docsPage.noResults}
                  </li>
                )}
                {matches.map((a) => (
                  <li key={a.slug}>
                    <button
                      type="button"
                      onClick={() => {
                        setSlug(a.slug);
                        setQuery('');
                      }}
                      className="block w-full py-1.5 text-left text-sm
                                 text-text-body hover:text-accent"
                    >
                      {title(a)}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <nav className="space-y-6">
                {DOCS.map((section) => (
                  <div key={section.titleRu}>
                    <h2 className="text-xs font-semibold uppercase tracking-wider
                                   text-text-muted">
                      {locale === 'ru' ? section.titleRu : section.titleEn}
                    </h2>
                    <ul className="mt-3 space-y-1">
                      {section.articles.map((a) => (
                        <li key={a.slug}>
                          <button
                            type="button"
                            onClick={() => setSlug(a.slug)}
                            className={cn(
                              'block w-full py-1.5 text-left text-sm transition-colors',
                              a.slug === slug
                                ? 'text-accent'
                                : 'text-text-body hover:text-text',
                            )}
                          >
                            {title(a)}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </nav>
            )}
          </aside>

          {/* Article */}
          <article className="min-w-0">
            {article && (
              <Card className="p-8">
                <h1 className="text-h3 font-bold text-text sm:text-h2">
                  {title(article)}
                </h1>
                <div className="mt-6">
                  {article.blocks.map((block, i) => (
                    <Block key={i} block={block} />
                  ))}
                </div>
              </Card>
            )}
          </article>
        </div>
      </Container>
    </>
  );
}
