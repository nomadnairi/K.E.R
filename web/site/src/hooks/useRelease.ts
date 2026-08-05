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
  assets?: GithubAsset[];
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

    fetch(LINKS.releasesLatestApi, {
      headers: { Accept: 'application/vnd.github+json' },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`GitHub responded ${r.status}`);
        return r.json() as Promise<GithubRelease>;
      })
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
