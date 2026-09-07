export type SpotState = { price: number; change: number; secondChange: number; time: Date | null; live: boolean };
export type RateState = { alis: number | null; satis: number | null; time: Date | null; live: boolean };
export type Quote = { alis: number; satis: number; dir: string; low: number; high: number; prev: number; time: string };
export type Tick = { time: number; price: number };
