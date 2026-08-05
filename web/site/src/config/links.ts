/** Every external destination the site points at, in one place. */
export const LINKS = {
  /** The real bot. Verified against README.md — not the mockup's placeholder. */
  telegramBot: 'https://t.me/jar_v1_s',
  telegramChannel: 'https://t.me/jar_v1_s',
  github: 'https://github.com/nomadnairi/K.E.R',
  releases: 'https://github.com/nomadnairi/K.E.R/releases',
  releasesLatestApi:
    'https://api.github.com/repos/nomadnairi/K.E.R/releases/latest',
  issues: 'https://github.com/nomadnairi/K.E.R/issues',
  license: 'https://github.com/nomadnairi/K.E.R/blob/main/LICENSE',
  dashboard: 'https://dashboard.ker-ai.online',
} as const;
