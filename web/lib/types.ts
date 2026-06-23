export type Config = {
  pairs: string[];
  tf: string;
  bias_tf: string;
  target_r: number;
  breakeven: number;
  broker: string;
  telegram: boolean;
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
  when?: string;
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
