export function Logo({ title = "RockHawk" }: { title?: string }) {
  return (
    <svg viewBox="0 0 64 64" role="img" aria-label={title}>
      <title>{title}</title>
      <path d="M4 46 L20 34 L32 40 L60 18" fill="none" stroke="#d4a24c" strokeWidth="3" />
      <path d="M18 46 L32 28 L46 38 L58 24" fill="none" stroke="#7ea36b" strokeWidth="2" />
      <path
        d="M28 30 C34 18 46 16 54 22 C46 22 42 26 40 32 C48 30 52 34 54 40 C44 36 34 38 28 44 C30 38 28 34 28 30Z"
        fill="#d4a24c"
      />
      <circle cx="48" cy="24" r="2.2" fill="#151b22" />
    </svg>
  );
}
