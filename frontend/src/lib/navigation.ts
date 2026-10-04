import { useEffect, useState } from 'react';
const NAVIGATION_EVENT = 'se:navigation';
export function useLocation(): { pathname: string; search: string } {
  const read = () => ({ pathname: window.location.pathname, search: window.location.search });
  const [location, setLocation] = useState(read);
  useEffect(() => {
    const changed = () => setLocation(read());
    window.addEventListener('popstate', changed); window.addEventListener(NAVIGATION_EVENT, changed);
    return () => { window.removeEventListener('popstate', changed); window.removeEventListener(NAVIGATION_EVENT, changed); };
  }, []);
  return location;
}
export function navigate(path: string, replace = false): void {
  const next = new URL(path, window.location.origin);
  if (next.origin !== window.location.origin || !path.startsWith('/') || path.startsWith('//')) return;
  window.history[replace ? 'replaceState' : 'pushState'](null, '', next.pathname + next.search);
  window.dispatchEvent(new Event(NAVIGATION_EVENT));
}
