/**
 * K.E.R. design tokens — the single source of truth for both the public site
 * and the dashboard.
 *
 * Nothing in a component may hardcode a colour. Everything goes through the
 * Tailwind theme generated from this file, which is what makes the two apps
 * (and the desktop Command Deck they echo) actually look like one product
 * instead of three things that were meant to match.
 */

export const colors = {
  /** Page background. Near-black with a green cast, not a neutral grey. */
  base: '#0A0F0A',
  /** Cards and panels sitting on the page. */
  elevated: '#10160F',
  /** Hover states and blocks nested inside a card. */
  raised: '#161D14',

  border: '#1C2A19',
  'border-strong': '#2A3D26',

  /**
   * The lime. Reserved for action and status only — a button, an active tab,
   * a live indicator. If everything is lime, nothing reads as clickable.
   */
  accent: '#7CE84A',
  'accent-hover': '#8FF25E',
  'accent-dim': '#5FB833',

  text: '#F0F5EE',
  'text-body': '#A8B8A2',
  'text-muted': '#6B7A66',

  danger: '#F2555A',
  warning: '#E8B84A',
} as const;

/** Accent at low alpha — glows, focus rings, chart fills. */
export const accentGlow = 'rgba(124, 232, 74, 0.18)';

export const radii = {
  pill: '999px',
  button: '8px',
  card: '12px',
} as const;

export const fonts = {
  sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
  mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
} as const;

/**
 * Type scale, in px, largest first. Headings are tight (-0.02em) and heavy;
 * body copy stays at 1.6 line-height and is capped at ~68 characters per line
 * by the `prose-measure` utility.
 */
export const fontSize = {
  display: '72px',
  h1: '56px',
  h2: '40px',
  h3: '28px',
  lead: '20px',
  body: '16px',
  sm: '14px',
  xs: '13px',
} as const;
