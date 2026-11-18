import { Component, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

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

createRoot(document.getElementById("root")!).render(<Boundary><App /></Boundary>);
