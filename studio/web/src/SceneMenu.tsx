// The scene actions (rename, delete, render order) behind a small menu
// button. They used to be options in the scene dropdown, where the arrow
// keys on a focused dropdown picked them one by one and opened the dialogs.
import { useEffect, useRef, useState } from "react";

export type SceneMenuItem = { label: string; run: () => void; disabled?: boolean; title?: string };

export function SceneMenu({ items, disabled }: { items: SceneMenuItem[]; disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    window.addEventListener("mousedown", away);
    return () => window.removeEventListener("mousedown", away);
  }, [open]);
  useEffect(() => {
    // the first item takes the focus, so the keyboard can use the menu
    if (open) (ref.current?.querySelector('[role="menuitem"]:not([disabled])') as HTMLElement | null)?.focus();
  }, [open]);
  return (
    <span className="scene-menu" ref={ref}
      onKeyDown={(e) => {
        if (!open) return;
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setOpen(false); (ref.current?.firstChild as HTMLElement)?.focus(); }
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
          e.preventDefault();
          e.stopPropagation();
          const all = [...(ref.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([disabled])') ?? [])];
          const i = all.indexOf(document.activeElement as HTMLElement);
          all[(i + (e.key === "ArrowDown" ? 1 : all.length - 1)) % all.length]?.focus();
        }
      }}>
      <button disabled={disabled} aria-haspopup="menu" aria-expanded={open} aria-label="Scene actions"
        title="Rename, delete or reorder scenes" onClick={() => setOpen((o) => !o)}>⋯</button>
      {open && (
        <span className="menu" role="menu">
          {items.map((it) => (
            <button key={it.label} role="menuitem" disabled={it.disabled} title={it.title}
              onClick={() => { setOpen(false); it.run(); }}>{it.label}</button>
          ))}
        </span>
      )}
    </span>
  );
}
