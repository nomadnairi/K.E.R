import { useEffect, useState } from 'react';

import { LINKS } from '../config/links';

export interface ReleaseAsset {
  name: string;
  size: number;
  url: string;
}

export interface Release {
  version: string;
  publishedAt: string;
  notesUrl: string;
  body: string;
  windows: ReleaseAsset | null;
}

interface State {
  release: Release | null;
  loading: boolean;
  failed: boolean;
}

interface GithubAsset {
  name: string;
  size: number;
  browser_download_url: string;
}

interface GithubRelease {
  tag_name: string;
  name?: string;
  published_at: string;
  html_url: string;
  body?: string;
  draft?: boolean;
  assets?: GithubAsset[];
}

/**
 * The newest published release, whether or not it is flagged as a prerelease.
 *
 * `/releases/latest` deliberately skips prereleases and drafts, so a project
 * that ships everything as a prerelease gets a bare 404 from it — and the
 * download page falls back to a plain link, looking as though nothing is
 * published at all. The full list does include them, so fall through to it.
 */
async function fetchNewestRelease(): Promise<GithubRelease> {
  const headers = { Accept: 'application/vnd.github+json' };

  const latest = await fetch(LINKS.releasesLatestApi, { headers });
  if (latest.ok) return (await latest.json()) as GithubRelease;
  if (latest.status !== 404) {
    throw new Error(`GitHub responded ${latest.status}`);
  }

  const all = await fetch(`${LINKS.releasesApi}?per_page=10`, { headers });
  if (!all.ok) throw new Error(`GitHub responded ${all.status}`);

  const published = ((await all.json()) as GithubRelease[]).find((r) => !r.draft);
  if (!published) throw new Error('no published release');
  return published;
}

function pickWindows(assets: GithubAsset[]): ReleaseAsset | null {
  const asset = assets.find((a) => /\.(exe|msi)$/i.test(a.name));
  if (!asset) return null;
  return { name: asset.name, size: asset.size, url: asset.browser_download_url };
}

/**
 * The latest release, straight from GitHub.
 *
 * Version and installer size are read at runtime rather than hardcoded: a
 * number baked into the page is wrong the moment the next release ships, and
 * a download page quoting the wrong version is worse than one quoting none.
 * Failure is surfaced (`failed`) so the UI can fall back to a plain link
 * instead of showing a blank card.
 */
export function useRelease(): State {
  const [state, setState] = useState<State>({
    release: null,
    loading: true,
    failed: false,
  });

  useEffect(() => {
    let alive = true;

    fetchNewestRelease()
      .then((data) => {
        if (!alive) return;
        setState({
          loading: false,
          failed: false,
          release: {
            version: data.tag_name?.replace(/^v/, '') ?? '',
            publishedAt: data.published_at ?? '',
            notesUrl: data.html_url ?? LINKS.releases,
            body: data.body ?? '',
            windows: pickWindows(data.assets ?? []),
          },
        });
      })
      .catch(() => {
        if (!alive) return;
        setState({ release: null, loading: false, failed: true });
      });

    return () => {
      alive = false;
    };
  }, []);

  return state;
}

export function formatSize(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
