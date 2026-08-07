import { kerPreset } from '@ker/ui/tailwind-preset';
import type { Config } from 'tailwindcss';

export default {
  presets: [kerPreset],
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
    // The shared kit lives outside this package — Tailwind has to scan it too
    // or its classes get purged out of the build.
    '../packages/ui/src/**/*.{ts,tsx}',
  ],
} satisfies Config;
