import { ButtonLink, Container, Pill } from '@ker/ui';
import { motion } from 'framer-motion';

import { CoreGraphic } from '../components/CoreGraphic';
import { LINKS } from '../config/links';
import { useT } from '../i18n';

const rise = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0 },
};

export function Hero() {
  const t = useT();

  return (
    <section className="relative overflow-hidden pt-28 sm:pt-32">
      <div className="pointer-events-none absolute inset-0 bg-tech-grid" />

      <Container className="relative">
        <div className="grid items-center gap-12 lg:grid-cols-[1.05fr_0.95fr]">
          <motion.div
            initial="hidden"
            animate="show"
            transition={{ staggerChildren: 0.08 }}
          >
            <motion.p
              variants={rise}
              className="text-xs font-semibold tracking-[0.2em] text-accent"
            >
              {t.hero.eyebrow}
            </motion.p>

            <motion.h1
              variants={rise}
              className="mt-5 text-[56px] font-extrabold leading-[0.95]
                         tracking-[0.06em] text-text sm:text-display"
            >
              {t.hero.title}
            </motion.h1>

            <motion.p
              variants={rise}
              className="mt-2 text-h3 font-bold leading-tight text-text sm:text-h2"
            >
              {t.hero.subtitle}
            </motion.p>

            <motion.p
              variants={rise}
              className="mt-4 text-lead font-medium text-accent"
            >
              {t.hero.tagline}
            </motion.p>

            <motion.p
              variants={rise}
              className="prose-measure mt-5 text-body text-text-body"
            >
              {t.hero.description}
            </motion.p>

            <motion.div variants={rise} className="mt-8 flex flex-wrap gap-3">
              <ButtonLink
                href={LINKS.telegramBot}
                target="_blank"
                rel="noreferrer"
                size="lg"
              >
                {t.hero.ctaPrimary}
              </ButtonLink>
              <ButtonLink
                href={LINKS.releases}
                target="_blank"
                rel="noreferrer"
                variant="secondary"
                size="lg"
              >
                {t.hero.ctaSecondary}
              </ButtonLink>
            </motion.div>

            <motion.div variants={rise} className="mt-9 flex flex-wrap gap-2.5">
              {t.hero.pills.map((pill) => (
                <Pill key={pill}>{pill}</Pill>
              ))}
            </motion.div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.94 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
            className="order-first lg:order-none"
          >
            <CoreGraphic className="mx-auto w-full max-w-[440px]" />
          </motion.div>
        </div>

        {/* Verifiable facts. The mockup had user counts and an uptime figure
            here; both were invented, and the brief bans exactly that. */}
        <div className="mt-16 border-t border-border py-8 sm:mt-20">
          <p className="text-xs font-semibold tracking-[0.18em] text-text-muted">
            {t.hero.factsLabel}
          </p>
          <dl className="mt-5 grid grid-cols-2 gap-6 sm:grid-cols-4">
            {t.hero.facts.map((fact) => (
              <div key={fact.label}>
                <dt className="text-h3 font-bold text-text">{fact.value}</dt>
                <dd className="mt-1 text-sm text-text-muted">{fact.label}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Container>
    </section>
  );
}
