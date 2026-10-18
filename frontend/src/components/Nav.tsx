import { NavLink, useLocation } from "react-router-dom";
import "./nav.css";

export function PrintMark({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden>
      <path d="M16 4c-6 0-10 4.5-10 10.5" />
      <path d="M26 14.5C26 8.5 22 4 16 4" />
      <path d="M9.5 15c0-3.8 2.9-6.6 6.5-6.6s6.5 2.8 6.5 6.6c0 4.2-.6 8.3-2 12" />
      <path d="M13 15.2c0-1.9 1.3-3.3 3-3.3s3 1.4 3 3.3c0 4.4-.8 8.6-2.6 12.4" />
      <path d="M16 15.5c0 5-1.4 9.5-4.2 13" />
      <path d="M6.5 19c.4 3.3 1.6 6.3 3.4 8.6" />
    </svg>
  );
}

export default function Nav() {
  const { pathname } = useLocation();
  const night = pathname === "/" || pathname === "/how-it-works";
  return (
    <header className={`nav ${night ? "nav-night" : ""}`}>
      <NavLink to="/" className="nav-mark" aria-label="Unmask, home">
        <PrintMark />
        <span>Unmask</span>
      </NavLink>
      <nav aria-label="Main">
        <NavLink to="/how-it-works">How it works</NavLink>
        <NavLink to="/case">Case file</NavLink>
        <NavLink to="/report">Dossier</NavLink>
      </nav>
    </header>
  );
}
