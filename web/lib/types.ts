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
  conf: number;
  size: number;
  tf?: string;
  why?: string;
  confluences?: string[];
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
  pairs: { pair: string; tf: Record<string, TFInfo> }[];
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
export type Analysis = {
  pair: string; tf: string; bias_tf: string; price: number; bias: string;
  breaks: Brk[]; fresh_snr: Zone[]; order_blocks: Zone[]; fvgs: Zone[]; sweeps: Sweep[];
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
