import { motion, useReducedMotion } from 'framer-motion';

/**
 * The hero visual: a wireframe core inside slowly turning orbital rings.
 *
 * Inline SVG rather than a raster or a 3D library — it stays sharp on any
 * display, weighs a couple of kilobytes instead of megabytes, and inherits the
 * theme's accent colour instead of baking it into a file. Motion is decorative,
 * so it stops entirely when the OS asks for reduced motion.
 */
export function CoreGraphic({ className = '' }: { className?: string }) {
  const still = useReducedMotion();

  const spin = (duration: number, reverse = false) =>
    still
      ? {}
      : {
          animate: { rotate: reverse ? -360 : 360 },
          transition: { duration, repeat: Infinity, ease: 'linear' as const },
        };

  return (
    <div className={`relative aspect-square ${className}`} aria-hidden="true">
      {/* Ambient glow behind everything. */}
      <div
        className="absolute inset-[15%] rounded-full bg-accent/20 blur-[80px]
                   animate-pulse-glow"
      />

      <svg viewBox="0 0 400 400" className="relative h-full w-full">
        <defs>
          <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#8FF25E" />
            <stop offset="100%" stopColor="#5FB833" />
          </linearGradient>
          <radialGradient id="coreFill">
            <stop offset="0%" stopColor="#7CE84A" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#7CE84A" stopOpacity="0.04" />
          </radialGradient>
        </defs>

        {/* Orbital rings, drawn as flattened ellipses for the isometric read. */}
        <motion.g
          style={{ originX: '200px', originY: '200px' }}
          {...spin(38)}
        >
          <ellipse
            cx="200" cy="200" rx="165" ry="58"
            fill="none" stroke="#2A3D26" strokeWidth="1"
          />
          <circle cx="365" cy="200" r="3.5" fill="#7CE84A" />
        </motion.g>

        <motion.g
          style={{ originX: '200px', originY: '200px' }}
          {...spin(56, true)}
        >
          <ellipse
            cx="200" cy="200" rx="120" ry="120"
            fill="none" stroke="#1C2A19" strokeWidth="1"
            strokeDasharray="4 10"
          />
        </motion.g>

        {/* The core: an isometric cube in wireframe. */}
        <motion.g
          animate={still ? {} : { y: [0, -10, 0] }}
          transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
        >
          <path
            d="M200 118 L272 160 v84 L200 286 L128 244 v-84 Z"
            fill="url(#coreFill)"
            stroke="url(#edge)"
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
          {/* Interior edges — what turns a hexagon into a cube. */}
          <path
            d="M200 202 L272 160 M200 202 v84 M200 202 L128 160"
            stroke="url(#edge)"
            strokeWidth="1.25"
            opacity="0.6"
          />
          <circle cx="200" cy="202" r="5" fill="#8FF25E" />
        </motion.g>
      </svg>
    </div>
  );
}
