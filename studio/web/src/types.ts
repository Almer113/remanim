// Shapes of what the studio server sends (studio/docs/protocol.md).

export type Span = [number, number, number, number];

export interface Anim {
  index: number;
  class: string;
  run_time: number;
  rate_func: string | null;
  default_rate_func: string | null;
  mobject: string | null;
  mobject_class: string | null;
}

export interface Clip {
  index: number;
  kind: "play" | "wait";
  start: number;
  duration: number;
  call: Span | null;
  call_name: string | null;
  func: string | null;
  line: number | null;
  lock: string | null;
  anims: Anim[];
  anim_runtimes: boolean[];
  play_runtime?: boolean;
  tier: number;
  text: string | null;
}

export interface Row {
  id: string | null;
  class: string | null;
  label: string;
  clips: { clip: number; anim: number }[];
}

export interface SceneModel {
  name: string;
  pending?: boolean;
  duration: number;
  error: { message: string; line: number | null } | null;
  bases: string[];
  target: number | null;
  clips: Clip[];
  rows: Row[];
  frames: number;
}

export interface Model {
  type: "model";
  file: string;
  rev: number;
  scenes: SceneModel[];
  fps: number;
  width: number;
  height: number;
  error: { code: string; message: string; line: number | null } | null;
  census: { statements: number; pct: Record<string, number> } | null;
  active: string | null;
  undo: boolean;
  redo: boolean;
  source: string;
}

export interface Obj {
  id: string;
  class: string;
  how: string;
  name: string | null;
  site: Span | null;
  user_site: Span | null;
  chain: string[];
  func: string | null;
  in_helper: boolean;
  params: string[];
  box: [number, number, number, number] | null;
  center?: [number, number];
  size?: [number, number];
  color?: string | null;
  values?: Record<string, number | string>;
  tier: number;
  call_text?: string;
  kwargs?: Record<string, string>;
  args?: string[];
}

export interface DiffHunk {
  line: number;
  before: string[];
  after: string[];
}
