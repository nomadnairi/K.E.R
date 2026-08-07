/**
 * The K.E.R. mark: an isometric cube outline, echoing the core graphic in the
 * hero and the desktop Command Deck. Drawn as SVG so it stays crisp at any
 * size and picks up `currentColor` from whatever it sits in.
 */
export function LogoMark({ className = 'h-6 w-6' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      aria-hidden="true"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
    >
      <path d="M12 2.5 21 7.5v9L12 21.5 3 16.5v-9L12 2.5Z" />
      <path d="M12 12 21 7.5M12 12v9.5M12 12 3 7.5" opacity="0.55" />
    </svg>
  );
}

export function Logo({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <LogoMark className="h-6 w-6 text-accent" />
      <span className="text-body font-extrabold tracking-[0.08em] text-text">
        K.E.R.
      </span>
    </span>
  );
}
