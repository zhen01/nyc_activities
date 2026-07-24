/**
 * Branded nav shell. Only "Discover" is a real, wired page this pass (see
 * plan's "Fully wired" / "Discover page only" scoping) -- Organizations
 * and Favorites render as inert labels, not links, so they don't imply
 * pages that don't exist yet.
 */

interface TopNavProps {
  favoritesCount: number;
}

export function TopNav({ favoritesCount }: TopNavProps) {
  return (
    <header className="top-nav">
      <div className="top-nav__brand">NYC Explorer</div>
      <nav className="top-nav__links">
        <span className="top-nav__link top-nav__link--active">Discover</span>
        <span className="top-nav__link" title="Coming soon">
          Organizations
        </span>
        <span className="top-nav__link" title="Coming soon">
          Favorites{favoritesCount > 0 ? ` (${favoritesCount})` : ""}
        </span>
      </nav>
    </header>
  );
}
