import { Agents } from '../sections/Agents';
import { Automation } from '../sections/Automation';
import { Desktop } from '../sections/Desktop';
import { Ecosystem } from '../sections/Ecosystem';
import { Faq } from '../sections/Faq';
import { Features } from '../sections/Features';
import { FinalCta } from '../sections/FinalCta';
import { Hero } from '../sections/Hero';
import { Memory } from '../sections/Memory';
import { Pricing } from '../sections/Pricing';
import { Security } from '../sections/Security';

/**
 * Home exists to explain the product in 20-30 seconds, in the order agreed in
 * the brief. Trust (Security) comes before the price, because someone handing
 * an assistant access to their PC needs that answered first.
 */
export function Home() {
  return (
    <>
      <Hero />
      <Ecosystem />
      <Features />
      <Memory />
      <Agents />
      <Automation />
      <Desktop />
      <Security />
      <Pricing />
      <Faq />
      <FinalCta />
    </>
  );
}
