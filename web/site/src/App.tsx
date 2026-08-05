import { useEffect } from 'react';
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
  useEffect(() => window.scrollTo(0, 0), [pathname]);
  return null;
}

function Layout() {
  const { pathname } = useLocation();
  const locale = localeFromPath(pathname);

  // Keep <html lang> honest for screen readers and search engines.
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  return (
    <LocaleContext.Provider value={locale}>
      <ScrollToTop />
      <Nav />
      <main className="min-h-screen">
        <Outlet />
      </main>
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
