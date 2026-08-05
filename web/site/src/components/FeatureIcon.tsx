export type FeatureKey =
  | 'memory'
  | 'agents'
  | 'actions'
  | 'automation'
  | 'integrations'
  | 'voice'
  | 'security'
  | 'multiplatform'
  | 'opensource';

/**
 * Outline icons, hand-drawn as SVG paths.
 *
 * An icon font or an icon package would be a network request and a few dozen
 * kilobytes for nine glyphs; these cost nothing and inherit `currentColor`.
 */
const PATHS: Record<FeatureKey, string> = {
  // Layers — stacked recollection.
  memory: 'M12 3 3 7.5 12 12l9-4.5L12 3ZM3 12l9 4.5L21 12M3 16.5 12 21l9-4.5',
  // A node delegating to nodes.
  agents:
    'M12 3v4M12 17v4M5.6 7.6 8.4 10M15.6 14l2.8 2.4M4 12h4M16 12h4 ' +
    'M12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Z',
  // Cursor acting on a window.
  actions: 'M4 4h16v11H4zM4 19h7M13 13l3 8 1.5-3.5L21 16l-8-3Z',
  // A clock with a repeat arrow.
  automation:
    'M12 7v5l3 2M20.5 12a8.5 8.5 0 1 1-2.6-6.1M20.5 3v5h-5',
  // Plug / connector.
  integrations:
    'M9 3v6M15 3v6M6.5 9h11v3a5.5 5.5 0 0 1-11 0V9ZM12 17.5V21',
  // Microphone.
  voice: 'M12 3.5a2.5 2.5 0 0 1 2.5 2.5v5a2.5 2.5 0 0 1-5 0V6A2.5 2.5 0 0 1 12 3.5ZM5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21',
  // Shield with a check.
  security: 'M12 3 5 6v5.5c0 4.3 2.9 8.2 7 9.5 4.1-1.3 7-5.2 7-9.5V6l-7-3ZM9 12l2 2 4-4',
  // Three surfaces.
  multiplatform: 'M3 5h12v9H3zM3 18h12M17 8h4v11h-4zM7 18v-4',
  // Code brackets.
  opensource: 'M9 6 4 12l5 6M15 6l5 6-5 6',
};

export function FeatureIcon({
  name,
  className = 'h-6 w-6',
}: {
  name: FeatureKey;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
