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
  /** seconds into its play() (clip(x, start=s)); 0 for most */
  offset?: number;
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
  /** per play() argument: a Transform-family pair, or null (step 8) */
  transforms?: ({ kind: string; source: string; target: string; kinds: string[] } | null)[];
  /** ordinal among the scene's play() clips (what timeline edits name) */
  play_index?: number;
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
  timed?: boolean;
  voice?: VoiceLine[];
  captions?: { text: string; start: number; end: number; line: number | null }[];
  burned_captions?: boolean;
  sounds?: { file: string; start: number; line: number | null }[];
  sections?: { index: number; name: string; start: number; line: number | null }[];
  /** begin_ambient_camera_rotation rates (step 10); span null when it can't be edited */
  ambient?: { line: number; span: Span | null; value: number | null; text: string }[];
}

export interface VoiceLine {
  index: number;
  kind: "say" | "voiceover";
  text: string;
  caption: string | null;
  start: number;
  requested: number;
  duration: number;
  hold: number;
  block_end: number | null;
  bookmarks: { name: string; t: number }[];
  line: number | null;
  lock: string | null;
  movable: boolean;
  warnings: string[];
}

export interface SoundWave {
  file: string;
  start: number;
  duration: number;
  peaks: number[];
  line?: number | null;  // the narration line this sound is, if any
}

export interface Model {
  type: "model";
  file: string;
  rev: number;
  session?: string;  // changes with every server run (frame URLs carry it)
  scenes: SceneModel[];
  fps: number;
  width: number;
  height: number;
  frame_width?: number;   // scene units across the frame (14.22 by default)
  frame_height?: number;
  error: { code: string; message: string; line: number | null } | null;
  census: { statements: number; pct: Record<string, number> } | null;
  active: string | null;
  undo: boolean;
  redo: boolean;
  source: string;
  /** Values the code peek can edit in place (tier 1-2 code; Phase 5). */
  literals?: Literal[];
}

export interface Literal {
  span: Span;               // as the server's edits use it (UTF-8 columns)
  line: number;
  cols: [number, number];   // start and end on that line, in characters
  kind: "number" | "string" | "name";
  text: string;             // as written in the file
  value?: string;           // strings: the text without quotes or escapes
  scope: "method" | "helper" | "constant";
}

export interface Obj {
  /** 3D: on-screen vectors of one world unit along x, y, z at the object (step 11) */
  proj?: { ex: number[]; ey: number[]; ez: number[] };
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
  /** a group the user made (`VGroup(a, b)`): no pixels of its own */
  virtual?: boolean;
  /** index into the same objects list of the group this one is in */
  parent?: number;
  p0?: [number, number];
  placement?: Record<string, unknown>;
  /** Text / MathTex / Tex: the string arguments, editable in place (Phase 5) */
  texts?: TextArg[];
  /** Axes ranges and lengths: each number the code peek could edit (span null: computed) */
  ranges?: { kw: string; parts: { span: Span | null; value: number | null; text: string; label: string }[] }[];
  /** A curve drawn from a lambda: its formula (Phase 5 step 7). */
  curve?: { params: string[]; expr: string; span: Span };
  updaters?: number;
}

/** A text's glyphs and the source characters behind each (GET /glyphs). */
export interface Glyphs {
  kind: "tex" | "text";
  parts: string[];
  map: [number, number, number][];   // per glyph: [part, start, end] in parts[part]
  boxes: [number, number, number, number][];   // scene units: x0, y0, x1, y1
  colors: (string | null)[];
}

/** The camera at a frame (GET /objects): a 2D moving camera's frame, or 3D angles in degrees. */
export type CameraState =
  | { kind: "2d"; center: [number, number]; width: number; height: number }
  | { kind: "3d"; phi: number; theta: number; gamma: number; zoom: number; focal_distance: number; center: number[] };

export interface TextArg {
  span: Span | null;     // null: the argument is computed, not a string literal
  value: string | null;
  editable: boolean;
  raw?: boolean;
  code?: string;
}

/** What the library panel hands to the canvas on drop. */
export type LibItem =
  | { kind: "shape"; class: string; entrance?: string }
  | { kind: "preset"; preset: string }
  /** several statements as one insert (Phase 5 step 12); `onObject`: dropped on an object */
  | { kind: "composite"; preset: string; onObject: boolean };

export interface DiffHunk {
  line: number;
  before: string[];
  after: string[];
}

/** Where a transform under the playhead is going (step 8), in scene units [x0, y0, x1, y1]. */
export interface Ghost {
  index: number;            // play() argument
  kind: string;
  target: number[] | null;
  pairs?: { key: string | null; to?: string | null; source: number[] | null; target: number[] | null; mapped?: boolean }[];
  unmatched_source?: { key: string | null; box: number[] | null }[];
  unmatched_target?: { key: string | null; box: number[] | null }[];
  keys?: boolean;           // TransformMatchingTex: keys are TeX text, so "match these" can write key_map
}
