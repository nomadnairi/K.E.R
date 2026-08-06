import { motion, useReducedMotion } from 'framer-motion';
import { useEffect, useLayoutEffect } from 'react';
import { Outlet, Route, Routes, useLocation } from 'react-router-dom';

import { Footer } from './components/Footer';
import { Nav } from './components/Nav';
import { LocaleContext, localeFromPath } from './i18n';
import { ChangelogPage } from './pages/ChangelogPage';
import { DocsPage } from './pages/DocsPage';
import { DownloadPage } from './pages/DownloadPage';
import { FeaturesPage } from './pages/FeaturesPage';
import { Home } from './pages/Home';
import { NotFound } from './pages/NotFound';
import { PricingPage } from './pages/PricingPage';
import { RoadmapPage } from './pages/RoadmapPage';
import { SecurityPage } from './pages/SecurityPage';

/** Land at the top of every page on navigation, as a normal site would. */
function ScrollToTop() {
  const { pathname } = useLocation();

  // Layout effect, not a plain one: this has to land before the browser paints
  // the new route, or the page is briefly visible at the old scroll offset.
  useLayoutEffect(() => {
    // `scroll-behavior: smooth` is set globally so in-page anchors glide. That
    // same rule turns this jump into a long crawl back up the page the user
    // has just left — the jankiest thing about navigating the site. `instant`
    // is the documented override for exactly this case; swapping the CSS
    // property around the call is not enough, because the scroll is still in
    // flight when the old value goes back on.
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [pathname]);

  return null;
}

function Layout() {
  const { pathname } = useLocation();
  const locale = localeFromPath(pathname);
  const still = useReducedMotion();

  // Keep <html lang> honest for screen readers and search engines.
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  return (
    <LocaleContext.Provider value={locale}>
      <ScrollToTop />
      <Nav />
      {/* Keyed on the path so each route plays its own entrance: without it a
          new page appears fully formed in the same frame the old one vanishes,
          which reads as a flicker rather than a transition. No exit animation —
          waiting for one to finish before drawing the next page costs more in
          felt latency than the polish is worth. */}
      {still ? (
        <main className="min-h-screen">
          <Outlet />
        </main>
      ) : (
        <motion.main
          key={pathname}
          className="min-h-screen"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
        >
          <Outlet />
        </motion.main>
      )}
      <Footer />
    </LocaleContext.Provider>
  );
}

export default function App() {
  return (
    <Routes>
      {/* Both locales run the same tree; the prefix only sets the dictionary. */}
      {['/', '/en'].map((prefix) => (
        <Route key={prefix} path={prefix} element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="features" element={<FeaturesPage />} />
          <Route path="pricing" element={<PricingPage />} />
          <Route path="download" element={<DownloadPage />} />
          <Route path="docs" element={<DocsPage />} />
          <Route path="security" element={<SecurityPage />} />
          <Route path="roadmap" element={<RoadmapPage />} />
          <Route path="changelog" element={<ChangelogPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      ))}
    </Routes>
  );
}
