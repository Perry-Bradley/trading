export type Config = {
  pairs: string[];
  tf: string;
  bias_tf: string;
  target_r: number;
  breakeven: number;
  broker: string;
  telegram: boolean;
  seed_state?: string;
};

export type PairOverview = {
  pair: string;
  bias: "long" | "short" | "flat";
  price: number;
  signal: boolean;
};

export type TrackRecord = {
  resolved: number;
  wins: number;
  win_rate: number;
  expectancy_r: number;
  total_r: number;
  total_pnl: number;
  profit_factor: number;
};

export type Signal = {
  pair: string;
  direction: "long" | "short";
  entry: number;
  stop: number;
  target: number;
  rr?: number;
  conf: number;
  size: number;
  tf?: string;
  time?: string;
  age_bars?: number;
  why?: string;
  confluences?: string[];
  features?: Record<string, any>;
  bar_idx?: number;
  tap_bar?: number;
  zone_top?: number;
  zone_bottom?: number;
  zone_kind?: string;
  tf_aligned?: boolean;
  aligned_tf?: string;
  active?: boolean;
};

export type Position = {
  pair: string;
  direction: "long" | "short";
  entry: number;
  stop: number;
  target: number;
  size: number;
};

export type Status = {
  broker: string;
  nav: number;
  target_r: number;
  breakeven: number;
  n_updates: number;
  track_record?: TrackRecord;
  open_positions: Position[];
  closed: any[];
  signals?: Signal[];
  overview?: PairOverview[];
  seed_state?: string;
  when?: string;
  tick_stats?: {
    signals_seen: number;
    eligible: number;
    conf_pass: number;
    blocked_dup: number;
    journal_rows: number;
    paper_closed: number;
  };
};

export type ModelInfo = {
  features: string[];
  target_r: number;
  breakeven: number;
  n_updates: number;
  coef: { feature: string; weight: number }[];
  cv_auc: number | null;
  seed_state?: string;
};

export type TFInfo = { bars: number; start: string; end: string } | null;
export type DataInfo = {
  pairs: { pair: string; tf: Record<string, TFInfo>; source?: string; live?: boolean }[];
  timeframes: string[];
  ladder: string;
  source: string;
  seed_state?: string;
};

export type BacktestRow = {
  pair: string;
  trades: number; wins: number; losses: number;
  win_rate: number; breakeven_wr: number;
  expectancy_r: number; total_r: number;
  avg_win_r: number; avg_loss_r: number;
  profit_factor: number | null; max_dd_r: number;
  error?: string;
};

export type Zone = { kind: string; top: number; bottom: number; time: string };
export type Brk = { type: string; dir: string; level: number; time: string };
export type Sweep = { side: string; level: number; time: string };
export type QM = { kind: string; sweep: number; choch: number; time: string };
export type Analysis = {
  pair: string; tf: string; bias_tf: string; price: number; bias: string;
  breaks: Brk[]; fresh_snr: Zone[]; order_blocks: Zone[]; fvgs: Zone[]; sweeps: Sweep[];
  breakers: Zone[]; quasimodos: QM[];
  last_bar?: string;
  now_utc?: string;
  stale_minutes?: number;
  seed_state?: string;
};

export type JournalRow = {
  ts: string;
  event: string;
  pair: string;
  direction: string;
  entry: string;
  stop: string;
  target: string;
  conf: string;
  size: string;
  outcome: string;
  r: string;
  pnl: string;
  nav: string;
};

export type JournalResponse = {
  rows: JournalRow[];
  count?: number;
  entries?: number;
  closes?: number;
  last_ts?: string | null;
};
