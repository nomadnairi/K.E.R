import { PageHeader } from '../components/PageHeader';
import { useT } from '../i18n';
import { Features } from '../sections/Features';
import { FinalCta } from '../sections/FinalCta';

/**
 * Purpose: show the real capabilities in one place, for someone comparing
 * K.E.R. against something else. Reuses the home grid instead of maintaining
 * a second copy of the same nine cards.
 */
export function FeaturesPage() {
  const t = useT();
  return (
    <>
      <PageHeader title={t.features.title} subtitle={t.features.subtitle} />
      <Features showAll={false} showHeader={false} />
      <FinalCta />
    </>
  );
}
