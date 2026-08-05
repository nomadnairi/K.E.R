/**
 * Tailwind preset built from the tokens.
 *
 * Both apps extend this instead of redeclaring a palette, so a change to
 * `tokens.ts` lands everywhere at once.
 */
import type { Config } from 'tailwindcss';

import { accentGlow, colors, fonts, fontSize, radii } from './tokens';

export const kerPreset = {
  content: [],
  theme: {
    extend: {
      colors,
      fontFamily: {
        sans: [...fonts.sans],
        mono: [...fonts.mono],
      },
      fontSize: {
        display: [fontSize.display, { lineHeight: '1.02', letterSpacing: '-0.02em' }],
        h1: [fontSize.h1, { lineHeight: '1.06', letterSpacing: '-0.02em' }],
        h2: [fontSize.h2, { lineHeight: '1.12', letterSpacing: '-0.02em' }],
        h3: [fontSize.h3, { lineHeight: '1.2', letterSpacing: '-0.01em' }],
        lead: [fontSize.lead, { lineHeight: '1.5' }],
        body: [fontSize.body, { lineHeight: '1.6' }],
        sm: [fontSize.sm, { lineHeight: '1.55' }],
        xs: [fontSize.xs, { lineHeight: '1.5' }],
      },
      borderRadius: {
        card: radii.card,
        button: radii.button,
        pill: radii.pill,
      },
      boxShadow: {
        /** The lime halo under a primary button / an active card. */
        glow: `0 0 0 1px ${accentGlow}, 0 8px 32px -8px ${accentGlow}`,
        'glow-lg': `0 0 60px -12px ${accentGlow}`,
      },
      backgroundImage: {
        /** The faint technical grid behind the hero. */
        grid: `linear-gradient(${colors.border} 1px, transparent 1px),
               linear-gradient(90deg, ${colors.border} 1px, transparent 1px)`,
      },
      backgroundSize: {
        grid: '48px 48px',
      },
      maxWidth: {
        /** ~68 characters — the readable measure for body copy. */
        measure: '34rem',
        container: '1200px',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-glow': {
          '0%, 100%': { opacity: '0.55' },
          '50%': { opacity: '1' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.5s cubic-bezier(0.16, 1, 0.3, 1) both',
        'pulse-glow': 'pulse-glow 4s ease-in-out infinite',
      },
    },
  },
} satisfies Partial<Config>;

export default kerPreset;
