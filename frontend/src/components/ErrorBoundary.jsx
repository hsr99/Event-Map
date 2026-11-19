import { Component } from 'react';

// Catches a crash in one page so visitors get a way out instead of a blank screen.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    console.error('Page crashed:', error, info?.componentStack);
  }

  componentDidUpdate(prevProps) {
    // Navigating to another page clears the error.
    if (this.state.failed && prevProps.resetKey !== this.props.resetKey) this.setState({ failed: false });
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="mx-auto max-w-md px-6 py-24 text-center">
        <h1 className="font-display text-5xl tracking-[0.02em]">Something broke</h1>
        <p className="mt-4 italic text-muted">This page hit an error. Reloading usually fixes it.</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-8 cursor-pointer bg-ink px-6 py-3 font-display text-lg tracking-[0.14em] text-ivory transition-colors hover:bg-teal-700 dark:bg-bone dark:text-ink dark:hover:bg-teal-400"
        >
          Reload
        </button>
      </div>
    );
  }
}
