import type { Dictionary } from './ru';

/**
 * English copy. Typed as `Dictionary`, so TypeScript rejects the build if a
 * key drifts from the Russian source — that is the whole mechanism keeping
 * the two locales in sync, and what makes adding UZ later a one-file job.
 */
export const en: Dictionary = {
  nav: {
    product: 'Product',
    features: 'Features',
    pricing: 'Pricing',
    download: 'Download',
    docs: 'Docs',
    security: 'Security',
    start: 'Get started',
  },

  hero: {
    eyebrow: 'PERSONAL AI CORE',
    title: 'K.E.R.',
    subtitle: 'YOUR PERSONAL AI ASSISTANT',
    tagline: 'Understands. Remembers. Acts.',
    description:
      'K.E.R. is not just a chat. It is your personal AI Core — it helps you ' +
      'work, controls your devices and automates the routine.',
    ctaPrimary: 'Start on Telegram',
    ctaSecondary: 'Download Desktop',
    pills: [
      'Memory without limits',
      'Agents and tools',
      'Access to every device',
      'Local or in the cloud',
      'Full control',
    ],
    factsLabel: 'WHAT THAT MEANS',
    facts: [
      { value: 'MIT', label: 'open source' },
      { value: '4', label: 'LLM providers, local ones included' },
      { value: '3', label: 'clients: Telegram, Desktop, Web' },
      { value: 'RU / EN / UZ', label: 'assistant languages' },
    ],
  },

  ecosystem: {
    title: 'One core. Any client.',
    subtitle: 'One account, one plan, one set of settings.',
    core: 'AI CORE',
    coreCaption: 'memory · agents · tools',
    clients: {
      telegram: { name: 'Telegram', caption: 'The fastest way in' },
      desktop: { name: 'Desktop', caption: 'Full access to your PC' },
      web: { name: 'Web', caption: 'From any browser' },
    },
    soon: 'Soon',
  },

  features: {
    title: 'What K.E.R. can do',
    subtitle: 'One assistant. Room to grow.',
    all: 'All features',
    items: {
      memory: {
        name: 'Memory',
        text: 'Remembers what matters and the context of your conversations',
      },
      agents: {
        name: 'Agents',
        text: 'Carry out tasks through sub-agents',
      },
      actions: {
        name: 'Actions',
        text: 'Controls your PC, files and applications',
      },
      automation: {
        name: 'Automation',
        text: 'Schedules, scenarios and triggers',
      },
      integrations: {
        name: 'Integrations',
        text: 'Smart home, weather, HTTP and any MCP server',
      },
      voice: {
        name: 'Voice',
        text: 'Natural conversation and spoken replies',
      },
      security: {
        name: 'Security',
        text: 'Local or in the cloud. Your data stays protected',
      },
      multiplatform: {
        name: 'Multiplatform',
        text: 'Telegram, Desktop, Web — one account',
      },
      opensource: {
        name: 'Open source',
        text: 'Transparency and freedom. MIT License',
      },
    },
  },

  memory: {
    title: 'Memory that works for you',
    subtitle: 'Not a chat log — knowledge about you.',
    points: [
      'Keeps context across sessions and restarts',
      'Distils durable facts out of conversations',
      'Finds things by meaning, not by matching words',
      'Passwords, tokens and card numbers are stripped before storage',
    ],
    demoUser: 'I keep my backups on drive D.',
    demoLater: 'a week later',
    demoAsk: 'Where should I put the project archive?',
    demoAnswer: 'On drive D — that is where you keep backups.',
  },

  agents: {
    title: 'Agents',
    subtitle: 'The assistant splits a task into steps and works through them.',
    steps: [
      { name: 'Task', text: 'You state the goal in plain words' },
      { name: 'Plan', text: 'The assistant breaks it into steps' },
      { name: 'Tools', text: 'It calls search, files, your PC, integrations' },
      { name: 'Result', text: 'It comes back with the answer' },
    ],
    note: 'Step count is capped so an agent cannot run forever.',
  },

  automation: {
    title: 'Automation',
    subtitle: 'It keeps working while you do something else.',
    items: [
      { name: 'Reminders', text: 'Say when — it reminds you on time' },
      { name: 'Schedules', text: 'A task repeats itself, without you' },
      { name: 'Proactivity', text: 'Noticed heavy system load — messages you first' },
    ],
    optIn: 'Proactive messages are opt-in and off by default.',
  },

  desktop: {
    title: 'The desktop app',
    subtitle: 'Command Deck — the assistant with access to your machine.',
    points: [
      'Opens sites and apps, types, presses keys',
      'Sees the screen when you turn sharing on',
      'Runs on its own model or through the server',
      'Every dangerous capability is off by default',
    ],
    cta: 'Download for Windows',
  },

  security: {
    title: 'Security',
    subtitle: 'An assistant with access to your PC has to earn that.',
    items: [
      {
        name: 'Off by default',
        text: 'Files, shell and PC control need explicit enabling',
      },
      {
        name: 'Three access states',
        text: 'Deny, ask every time, or allow',
      },
      {
        name: 'Audit log',
        text: 'Every use of a capability is recorded',
      },
      {
        name: 'Secrets are not stored',
        text: 'Passwords and tokens are stripped before memory is written',
      },
      {
        name: 'Your key, your model',
        text: 'BYOK or a local model — data never leaves the machine',
      },
      {
        name: 'Open source',
        text: 'Check it yourself: MIT-licensed source on GitHub',
      },
    ],
    honest:
      'End-to-end encryption is in development and is not claimed as ' +
      'working yet.',
  },

  pricing: {
    title: 'Pricing',
    subtitle: 'Honest prices. Transparent limits.',
    popular: 'Popular',
    perMonth: 'per month',
    free: 'Free',
    stars: 'Stars',
    note: 'Paid with Telegram Stars · No card · Cancel any time',
    cta: { free: 'Try for free', paid: 'Choose' },
    tiers: {
      free: { name: 'Free', caption: 'To get to know K.E.R.' },
      plus: { name: 'Plus', caption: 'For everyday use' },
      pro: { name: 'Pro', caption: 'For professionals' },
    },
    limits: {
      messages: 'messages per day',
      messagesUnlimited: 'Unlimited messages',
      integrations: ['integration', 'integrations', 'integrations'] as [
        string,
        string,
        string,
      ],
      integrationsUnlimited: 'Unlimited integrations',
    },
    perks: {
      memory: 'Personal memory',
      allModels: 'Every model',
      images: 'Image generation',
      api: 'API access',
      desktop: 'PC actions and screen sharing',
      priority: 'Priority processing',
    },
  },

  faq: {
    title: 'Questions',
    items: [
      {
        q: 'How is this different from a normal chatbot?',
        a: 'K.E.R. remembers you between conversations and takes action — ' +
          'opens apps, works with files, runs scheduled tasks. A normal ' +
          'chat only answers.',
      },
      {
        q: 'Do I need a bank card?',
        a: 'No. Payment goes through Telegram Stars, and the free tier is ' +
          'available immediately without paying.',
      },
      {
        q: 'Does my data go to your server?',
        a: 'It depends how you run K.E.R. Through the bot, requests go via ' +
          'the server. With a local model or your own key, they do not.',
      },
      {
        q: 'Does it really control the computer?',
        a: 'Yes, but only if you allowed it. Access to files, the shell and ' +
          'PC control is off by default.',
      },
      {
        q: 'Does one account work across all clients?',
        a: 'Yes. Telegram, Desktop and Web are entrances to one core: one ' +
          'account, one plan, one set of settings. Conversation history is ' +
          'still per-client for now.',
      },
      {
        q: 'Can I self-host it?',
        a: 'Yes, the source is open under MIT. Run it on your own server or ' +
          'computer.',
      },
    ],
  },

  download: {
    title: 'Download K.E.R.',
    subtitle: 'Pick your platform.',
    windows: 'K.E.R. for Windows',
    installer: 'Full installer',
    download: 'Download',
    version: 'Version',
    size: 'Size',
    checksum: 'Verify integrity (SHA256)',
    releaseNotes: 'Release notes',
    sourceCode: 'Source code',
    sourceCaption: 'GitHub Repository',
    loading: 'Loading release data…',
    failed: 'Could not fetch the release. Open the releases page instead.',
    requirements: 'Windows 10/11, 64-bit',
    otherPlatforms: 'Other platforms',
    linuxNote: 'No build yet — can be run from source',
    androidNote: 'The client is in the repository, no packaged build yet',
  },

  roadmapPage: {
    title: 'Roadmap',
    subtitle: 'What is done and what is ahead. No backdated promises.',
    done: 'Done',
    partial: 'Partial',
    planned: 'Planned',
    source: 'The list is maintained in ROADMAP.md in the repository.',
  },

  changelogPage: {
    title: 'Changelog',
    subtitle: 'Release history.',
    loading: 'Loading releases…',
    failed: 'Could not fetch releases. Open the releases page on GitHub.',
    viewOnGithub: 'View on GitHub',
  },

  docsPage: {
    title: 'Documentation',
    subtitle: 'How to start and how to configure.',
    search: 'Search the docs',
    noResults: 'Nothing found',
    onThisPage: 'On this page',
  },

  footer: {
    tagline: 'Personal AI Core.',
    product: 'Product',
    resources: 'Resources',
    community: 'Community',
    roadmap: 'Roadmap',
    changelog: 'Changelog',
    github: 'GitHub',
    telegram: 'Telegram',
    channel: 'Channel',
    license: 'MIT License',
    rights: 'Open source.',
  },

  common: {
    soon: 'Soon',
    readMore: 'Read more',
  },
};
