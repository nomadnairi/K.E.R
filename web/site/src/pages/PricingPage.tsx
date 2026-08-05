import { PageHeader } from '../components/PageHeader';
import { useT } from '../i18n';
import { Faq } from '../sections/Faq';
import { Pricing } from '../sections/Pricing';

/** Purpose: pick a tier. Cards, then the questions that block a purchase. */
export function PricingPage() {
  const t = useT();
  return (
    <>
      <PageHeader title={t.pricing.title} subtitle={t.pricing.subtitle} />
      <Pricing showHeader={false} />
      <Faq />
    </>
  );
}
