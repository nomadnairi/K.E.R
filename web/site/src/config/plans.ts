/**
 * Subscription tiers — mirrored from `jarvis/billing/plans.py`.
 *
 * THIS MUST MATCH WHAT THE BOT ACTUALLY CHARGES. The site showing one price
 * while Telegram bills another is the fastest way to lose a first customer's
 * trust, so every number here is copied from the Python source and nothing is
 * rounded "for the landing page".
 *
 * Source values (`jarvis/billing/plans.py:91-110`):
 *   FREE  daily_messages=10,  integrations=2, price_stars=0
 *   PLUS  daily_messages=100, integrations=6, price_stars=2500
 *   PRO   daily_messages=0 (unlimited), integrations=0 (unlimited),
 *         price_stars=8000
 *
 * Open question for the owner: the approved mockup showed 299 ₽ / 899 ₽,
 * which is ~15x below the Stars figures above. Until that is settled, the
 * code's numbers stand — change them here and nowhere else.
 */

export type TierId = 'free' | 'plus' | 'pro';

export interface Plan {
  id: TierId;
  /** Price in Telegram Stars. 0 = free. */
  priceStars: number;
  /** Messages per day. `null` = unlimited. */
  dailyMessages: number | null;
  /** Connected integrations. `null` = unlimited. */
  integrations: number | null;
  featured: boolean;
}

export const PLANS: readonly Plan[] = [
  {
    id: 'free',
    priceStars: 0,
    dailyMessages: 10,
    integrations: 2,
    featured: false,
  },
  {
    id: 'plus',
    priceStars: 2500,
    dailyMessages: 100,
    integrations: 6,
    featured: true,
  },
  {
    id: 'pro',
    priceStars: 8000,
    dailyMessages: null,
    integrations: null,
    featured: false,
  },
] as const;
