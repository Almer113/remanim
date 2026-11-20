// Every app shortcut in one table (Phase 6 step 6). The key handler, the
// tooltips (`tip`) and the help sheet all read it, so they can't disagree.
// Overlays (glyph picker, text editor, camera mode, dialogs) keep their own
// keys and switch these off while they are open.

export type Action =
  | "play" | "back" | "forward" | "back1s" | "forward1s" | "start" | "end" | "prevClip" | "nextClip"
  | "nudgeLeft" | "nudgeRight" | "nudgeUp" | "nudgeDown"
  | "undo" | "redo" | "duplicate" | "group" | "delete" | "clear"
  | "export" | "help" | "ripple" | "marker";

export interface Binding {
  action: Action;
  keys: string[];          // as shown: "Ctrl+Z", "Space", "←"
  label: string;
  group: "Playback" | "Objects" | "Edit" | "Timeline" | "App";
  // matches: key (KeyboardEvent.key, lower-case for letters), modifiers
  match: { key: string; ctrl?: boolean; shift?: boolean | "any"; alt?: boolean | "any"; sel?: boolean }[];
}

// sel: true = only with an object selected; false = only without one
export const BINDINGS: Binding[] = [
  { action: "play", keys: ["Space", "K"], label: "Play / pause", group: "Playback",
    match: [{ key: " " }, { key: "k" }] },
  { action: "back", keys: ["←", ","], label: "One frame back (← when nothing is selected)", group: "Playback",
    match: [{ key: "arrowleft", sel: false }, { key: "," }] },
  { action: "forward", keys: ["→", "."], label: "One frame on (→ when nothing is selected)", group: "Playback",
    match: [{ key: "arrowright", sel: false }, { key: "." }] },
  { action: "back1s", keys: ["J", "Shift+←"], label: "One second back", group: "Playback",
    match: [{ key: "j" }, { key: "arrowleft", shift: true, sel: false }] },
  { action: "forward1s", keys: ["L", "Shift+→"], label: "One second on", group: "Playback",
    match: [{ key: "l" }, { key: "arrowright", shift: true, sel: false }] },
  { action: "start", keys: ["Home"], label: "Start of the scene", group: "Playback", match: [{ key: "home" }] },
  { action: "end", keys: ["End"], label: "End of the scene", group: "Playback", match: [{ key: "end" }] },
  { action: "prevClip", keys: ["["], label: "Previous clip start", group: "Playback", match: [{ key: "[" }] },
  { action: "nextClip", keys: ["]"], label: "Next clip start", group: "Playback", match: [{ key: "]" }] },

  { action: "nudgeLeft", keys: ["←"], label: "Nudge the selection left (Shift ×10, Alt fine)", group: "Objects",
    match: [{ key: "arrowleft", sel: true, shift: "any", alt: "any" }] },
  { action: "nudgeRight", keys: ["→"], label: "Nudge right", group: "Objects",
    match: [{ key: "arrowright", sel: true, shift: "any", alt: "any" }] },
  { action: "nudgeUp", keys: ["↑"], label: "Nudge up", group: "Objects",
    match: [{ key: "arrowup", sel: true, shift: "any", alt: "any" }] },
  { action: "nudgeDown", keys: ["↓"], label: "Nudge down", group: "Objects",
    match: [{ key: "arrowdown", sel: true, shift: "any", alt: "any" }] },
  { action: "duplicate", keys: ["Ctrl+D"], label: "Duplicate", group: "Objects", match: [{ key: "d", ctrl: true }] },
  { action: "group", keys: ["Ctrl+G"], label: "Group the selection (Shift-click adds objects)", group: "Objects",
    match: [{ key: "g", ctrl: true }] },
  { action: "delete", keys: ["Delete", "Backspace"], label: "Delete the selection", group: "Objects",
    match: [{ key: "delete" }, { key: "backspace" }] },
  { action: "clear", keys: ["Esc"], label: "Clear the selection", group: "Objects", match: [{ key: "escape" }] },

  { action: "undo", keys: ["Ctrl+Z"], label: "Undo", group: "Edit", match: [{ key: "z", ctrl: true }] },
  { action: "redo", keys: ["Ctrl+Shift+Z", "Ctrl+Y"], label: "Redo", group: "Edit",
    match: [{ key: "z", ctrl: true, shift: true }, { key: "y", ctrl: true }] },

  { action: "ripple", keys: ["R"], label: "Ripple on / off", group: "Timeline", match: [{ key: "r" }] },
  { action: "marker", keys: ["M"], label: "Marker at the playhead", group: "Timeline", match: [{ key: "m" }] },

  { action: "export", keys: ["Ctrl+E"], label: "Export video", group: "App", match: [{ key: "e", ctrl: true }] },
  { action: "help", keys: ["?"], label: "Show the keyboard shortcuts", group: "App", match: [{ key: "?", shift: "any" }] },
];

/** The action for a key press, or null. `selected`: an object is selected. */
export function actionFor(e: KeyboardEvent, selected: boolean): Action | null {
  const key = e.key.toLowerCase();
  const ctrl = e.ctrlKey || e.metaKey;
  for (const b of BINDINGS) {
    for (const m of b.match) {
      if (m.key !== key) continue;
      if (!!m.ctrl !== ctrl) continue;
      if (m.shift !== "any" && !!m.shift !== e.shiftKey) continue;
      if (m.alt !== "any" && !!m.alt !== e.altKey) continue;
      if (m.sel !== undefined && m.sel !== selected) continue;
      return b.action;
    }
  }
  return null;
}

/** "Undo (Ctrl+Z)" for a tooltip. */
export function tip(action: Action, text?: string): string {
  const b = BINDINGS.find((x) => x.action === action);
  return b ? `${text ?? b.label} (${b.keys.join(" / ")})` : text ?? "";
}

/** Nudge distance in scene units: Shift ×10, Alt fine. */
export function nudgeStep(e: { shiftKey: boolean; altKey: boolean }): number {
  return e.altKey ? 0.02 : e.shiftKey ? 1 : 0.1;
}
