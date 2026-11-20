import { Component, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";
import "./probe";  // window.__frameProbe, idle until started

/** A render error shows a message and a way back instead of a blank page. */
class Boundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="empty">
        <p>The studio hit a bug and stopped drawing: {String(this.state.error.message)}</p>
        <p>Your .py file is safe; nothing is written without a verified edit.</p>
        <button onClick={() => location.reload()}>Reload the studio</button>
      </div>
    );
  }
}

/** Buttons are named by their text, with the tooltip as a description (Phase 7
 * step 12): "+ New file", not "A new scene file from the studio template".
 * Icon-only buttons (◀, ?, ⏮) keep their tooltip as the name. */
function nameButtons(root: ParentNode) {
  root.querySelectorAll?.("button[title]").forEach((b) => {
    const text = (b.textContent ?? "").replace(/\s+/g, " ").trim();
    const title = b.getAttribute("title") ?? "";
    if (!/[A-Za-z]{2}/.test(text) || b.hasAttribute("data-own-label")) return;
    if (b.getAttribute("aria-label") !== text) b.setAttribute("aria-label", text);
    if (title && title !== text && b.getAttribute("aria-description") !== title) b.setAttribute("aria-description", title);
  });
}
new MutationObserver(() => nameButtons(document)).observe(document.body,
  { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ["title"] });

createRoot(document.getElementById("root")!).render(<Boundary><App /></Boundary>);
