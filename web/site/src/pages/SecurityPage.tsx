import { PageHeader } from '../components/PageHeader';
import { useT } from '../i18n';
import { FinalCta } from '../sections/FinalCta';
import { Security } from '../sections/Security';

/** Purpose: answer "can I trust this with access to my machine?". */
export function SecurityPage() {
  const t = useT();
  return (
    <>
      <PageHeader title={t.security.title} subtitle={t.security.subtitle} />
      <Security showHeader={false} />
      <FinalCta />
    </>
  );
}
