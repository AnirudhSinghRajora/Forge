import { useEffect, useState } from "react";

// A tiny pushState router. The app has seven routes, none of them nested.
const EVT = "fs:navigate";

export function navigate(to: string, opts: { replace?: boolean; keepScroll?: boolean } = {}) {
  if (opts.replace) history.replaceState(null, "", to);
  else history.pushState(null, "", to);
  window.dispatchEvent(new Event(EVT));
  if (!opts.keepScroll) window.scrollTo(0, 0);
}

export function useLocationPath() {
  const read = () => ({ path: location.pathname, search: location.search });
  const [loc, setLoc] = useState(read);
  useEffect(() => {
    const on = () => setLoc(read());
    window.addEventListener("popstate", on);
    window.addEventListener(EVT, on);
    return () => {
      window.removeEventListener("popstate", on);
      window.removeEventListener(EVT, on);
    };
  }, []);
  return loc;
}

export function linkProps(to: string) {
  return {
    href: to,
    onClick: (e: React.MouseEvent) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
      e.preventDefault();
      navigate(to);
    },
  };
}
