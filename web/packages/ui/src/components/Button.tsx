import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react';

import { cn } from '../cn';

type Variant = 'primary' | 'secondary' | 'ghost';
type Size = 'md' | 'lg';

const VARIANTS: Record<Variant, string> = {
  // Lime fill, dark text — the one thing on a screen the eye should land on.
  primary:
    'bg-accent text-base font-semibold hover:bg-accent-hover hover:shadow-glow ' +
    'active:translate-y-px',
  secondary:
    'border border-border-strong text-text hover:border-accent-dim ' +
    'hover:bg-raised',
  ghost: 'text-text-body hover:text-text hover:bg-raised',
};

const SIZES: Record<Size, string> = {
  md: 'h-10 px-4 text-sm gap-2',
  lg: 'h-12 px-6 text-body gap-2.5',
};

const BASE =
  'inline-flex items-center justify-center rounded-button transition-all ' +
  'duration-200 whitespace-nowrap focus-visible:outline-none ' +
  'focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 ' +
  'focus-visible:ring-offset-base disabled:opacity-50 ' +
  'disabled:pointer-events-none';

interface CommonProps {
  variant?: Variant;
  size?: Size;
  className?: string;
  children: ReactNode;
}

type ButtonProps = CommonProps & ButtonHTMLAttributes<HTMLButtonElement>;
type LinkProps = CommonProps & AnchorHTMLAttributes<HTMLAnchorElement> & { href: string };

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button className={cn(BASE, VARIANTS[variant], SIZES[size], className)} {...rest}>
      {children}
    </button>
  );
}

/** Same skin, rendered as a link — for CTAs that navigate rather than act. */
export function ButtonLink({
  variant = 'primary',
  size = 'md',
  className,
  children,
  ...rest
}: LinkProps) {
  return (
    <a className={cn(BASE, VARIANTS[variant], SIZES[size], className)} {...rest}>
      {children}
    </a>
  );
}
