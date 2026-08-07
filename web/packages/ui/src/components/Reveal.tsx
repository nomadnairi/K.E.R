import { motion, useReducedMotion } from 'framer-motion';
import type { ReactNode } from 'react';

/**
 * Fade-and-rise a block the first time it scrolls into view.
 *
 * Two things this gets right that a bare `whileInView` does not:
 *
 * 1. With `prefers-reduced-motion` it renders the children plainly — Framer
 *    animates via JS transforms, so the CSS reduced-motion override in
 *    `styles.css` would not have touched it.
 * 2. The hidden state is opacity-only and is forced back on for print, so a
 *    printed page (or anything that never fires an IntersectionObserver)
 *    cannot end up with invisible sections.
 */
export function Reveal({
  delay = 0,
  className,
  children,
}: {
  delay?: number;
  className?: string;
  children: ReactNode;
}) {
  const still = useReducedMotion();

  if (still) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}
