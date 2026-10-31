// Hand-drawn line icons. Icons always travel with a short word, because some users read little.
const P: Record<string, React.ReactNode> = {
  mic: (<><rect x="9" y="2.5" width="6" height="12" rx="3" /><path d="M5 11.5a7 7 0 0 0 14 0M12 18.5V22M8.5 22h7" /></>),
  stop: <rect x="6" y="6" width="12" height="12" rx="1.5" />,
  pin: (<><path d="M12 22s7-7.2 7-12.5A7 7 0 0 0 5 9.5C5 14.8 12 22 12 22z" /><circle cx="12" cy="9.5" r="2.5" /></>),
  gps: (<><circle cx="12" cy="12" r="6.5" /><circle cx="12" cy="12" r="1.5" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></>),
  field: (<><path d="M3 20 8 8h8l5 12H3z" /><path d="M9.5 8 8 20M14.5 8 16 20M5.8 14h12.4" /></>),
  satellite: (<><path d="m9 9 6 6M6.5 11.5l-3-3 3-3 3 3M12.5 17.5l3 3 3-3-3-3" /><path d="M10 10 13.5 6.5 17.5 10.5 14 14z" /><path d="M16 21a5 5 0 0 0 5-5" /></>),
  radar: (<><path d="M3 12a9 9 0 0 1 9-9M6.5 12A5.5 5.5 0 0 1 12 6.5" /><circle cx="12" cy="12" r="1.8" /><path d="M13.5 13.5 21 21M21 12a9 9 0 0 1-9 9" /></>),
  cloud: (<><path d="M7 18a4 4 0 0 1-.5-8A5.5 5.5 0 0 1 17 9.2 4.4 4.4 0 0 1 17 18H7z" /></>),
  doc: (<><path d="M6 2.5h8.5L19 7v14.5H6z" /><path d="M14.5 2.5V7H19M9 12h7M9 16h7" /></>),
  scale: (<><path d="M12 3v18M7 21h10M5 6.5h14" /><path d="m5 6.5-3 7a3.2 3.2 0 0 0 6 0l-3-7zM19 6.5l-3 7a3.2 3.2 0 0 0 6 0l-3-7z" /></>),
  phone: (<path d="M5 3h4l1.8 5-2.3 1.6a12 12 0 0 0 5.9 5.9L16 13.2l5 1.8v4a2 2 0 0 1-2.2 2A17 17 0 0 1 3 5.2 2 2 0 0 1 5 3z" />),
  share: (<><circle cx="18" cy="5" r="2.6" /><circle cx="6" cy="12" r="2.6" /><circle cx="18" cy="19" r="2.6" /><path d="m8.3 10.7 7.4-4.4M8.3 13.3l7.4 4.4" /></>),
  copy: (<><rect x="8.5" y="8.5" width="12" height="12.5" /><path d="M15.5 8.5V3H3.5v12.5h5" /></>),
  download: (<path d="M12 3v12M7 10.5l5 5 5-5M4 20.5h16" />),
  play: <path d="M7 4v16l13-8z" />,
  pause: <path d="M7 4h3.5v16H7zM13.5 4H17v16h-3.5z" />,
  undo: (<path d="M8 6 3.5 10.5 8 15M4 10.5h10a6 6 0 0 1 0 12h-3" />),
  trash: (<path d="M4 6.5h16M9 6.5V3.5h6v3M6.5 6.5 8 21h8l1.5-14.5" />),
  check: <path d="m4 12.5 5.5 5.5L20 6.5" />,
  cross: <path d="m5 5 14 14M19 5 5 19" />,
  arrow: <path d="M4 12h15M13 6l6 6-6 6" />,
  back: <path d="M20 12H5M11 6l-6 6 6 6" />,
  clock: (<><circle cx="12" cy="12" r="9" /><path d="M12 7v5.5l3.5 2" /></>),
  warn: (<><path d="M12 3.5 22 20.5H2z" /><path d="M12 10v5M12 17.8v.2" /></>),
  retry: (<path d="M20 11a8 8 0 1 0-2.3 6.2M20 4.5V11h-6.5" />),
  edit: (<path d="M4 20.5l1-4.5L16.5 4.5l3.5 3.5L8.5 19.5zM14 7l3.5 3.5" />),
  question: (<><path d="M8.5 9a3.5 3.5 0 1 1 5.6 2.8c-1.3 1-2.1 1.7-2.1 3.2" /><path d="M12 18.8v.2" /></>),
  hand: (<path d="M8 12V5.5a1.5 1.5 0 0 1 3 0V11m0-7a1.5 1.5 0 0 1 3 0v7m0-5a1.5 1.5 0 0 1 3 0v8.5a7 7 0 0 1-7 7c-3 0-4.6-1.6-6-4l-2.2-3.6a1.5 1.5 0 0 1 2.5-1.6L8 15" />),
  hail: (<><path d="M7 14a4 4 0 0 1-.5-8A5.5 5.5 0 0 1 17 5.2 4.4 4.4 0 0 1 17 14H7z" /><circle cx="8" cy="18" r="1.3" /><circle cx="12.5" cy="20.5" r="1.3" /><circle cx="16.5" cy="18" r="1.3" /></>),
  rain: (<><path d="M7 14a4 4 0 0 1-.5-8A5.5 5.5 0 0 1 17 5.2 4.4 4.4 0 0 1 17 14H7z" /><path d="m9 17-1.5 4M13 17l-1.5 4M17 17l-1.5 4" /></>),
  flood: (<><path d="M3 18c2 0 2-1.5 4.5-1.5S10 18 12 18s2-1.5 4.5-1.5S19 18 21 18M3 22c2 0 2-1.5 4.5-1.5S10 22 12 22s2-1.5 4.5-1.5S19 22 21 22" /><path d="M5 13V8l7-5 7 5v5" /></>),
  cyclone: (<path d="M21 6.5C17 4 13 4 10 5.2 6 7 4.5 11 6 14.2c1.4 3 5.3 4.2 8 2.4 2.3-1.5 2.6-5 .7-6.6-1.7-1.4-4.4-.7-5 1.4M3 17.5c4 2.5 8 2.5 11 1.3" />),
  wind: (<path d="M3 9h11a3 3 0 1 0-3-3M3 14h16a2.7 2.7 0 1 1-2.7 2.7M3 19h7" />),
  pest: (<><ellipse cx="12" cy="13.5" rx="4.2" ry="6" /><path d="M12 7.5V4M9.5 5 8 3M14.5 5 16 3M8 11 3.5 9M16 11l4.5-2M7.8 14.5H3M16.2 14.5H21M8.5 17.5 5 20M15.5 17.5 19 20" /></>),
  sun: (<><circle cx="12" cy="12" r="4.5" /><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M5 5l1.8 1.8M17.2 17.2 19 19M5 19l1.8-1.8M17.2 6.8 19 5" /></>),
  other: (<><circle cx="5.5" cy="12" r="1.7" /><circle cx="12" cy="12" r="1.7" /><circle cx="18.5" cy="12" r="1.7" /></>),
  link: (<path d="M10 14a4.5 4.5 0 0 0 6.4 0l3.1-3.1a4.5 4.5 0 0 0-6.4-6.4l-1.4 1.4M14 10a4.5 4.5 0 0 0-6.4 0L4.5 13.1a4.5 4.5 0 0 0 6.4 6.4l1.4-1.4" />),
};

export type IconName = keyof typeof P | string;

export function Icon({ name, size = 22, stroke = 1.7 }: { name: IconName; size?: number; stroke?: number }) {
  return (
    <svg
      className="icon"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {P[name] ?? null}
    </svg>
  );
}
