export function PolarisLogo({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-label="POLARIS">
      <polygon
        points="32,4 38,22 56,18 42,32 56,46 38,42 32,60 26,42 8,46 22,32 8,18 26,22"
        fill="#52607A"
        transform="rotate(30 32 32)"
      />
      <polygon
        points="32,4 38,22 56,18 42,32 56,46 38,42 32,60 26,42 8,46 22,32 8,18 26,22"
        fill="#CBD5E1"
      />
      <circle cx="32" cy="32" r="10" stroke="#475569" strokeWidth="1.2" fill="none" />
      <circle cx="32" cy="32" r="5" stroke="#475569" strokeWidth="1" fill="none" />
    </svg>
  );
}
