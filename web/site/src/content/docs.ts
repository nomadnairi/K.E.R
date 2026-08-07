/**
 * User documentation.
 *
 * Written for this site: `docs/` in the repository holds operator material
 * (infrastructure, security audits), not end-user guides. Content is plain
 * structured data rather than MDX so search can index it without a build
 * plugin, and so the whole set stays translatable through the same mechanism
 * as the rest of the site.
 */
export interface DocBlock {
  kind: 'text' | 'steps' | 'note' | 'code';
  ru: string | string[];
  en: string | string[];
}

export interface DocArticle {
  slug: string;
  titleRu: string;
  titleEn: string;
  blocks: DocBlock[];
}

export interface DocSection {
  titleRu: string;
  titleEn: string;
  articles: DocArticle[];
}

export const DOCS: readonly DocSection[] = [
  {
    titleRu: 'Начало работы',
    titleEn: 'Getting started',
    articles: [
      {
        slug: 'quick-start',
        titleRu: 'Быстрый старт',
        titleEn: 'Quick start',
        blocks: [
          {
            kind: 'text',
            ru: 'K.E.R. запускается за три шага. Аккаунт создаётся сам при первом входе — регистрироваться отдельно не нужно.',
            en: 'K.E.R. takes three steps to start. Your account is created on first sign-in — there is no separate registration.',
          },
          {
            kind: 'steps',
            ru: [
              'Откройте бота @jar_v1_s в Telegram и нажмите «Начать».',
              'Скачайте приложение для Windows со страницы «Скачать».',
              'В приложении выберите вход по коду — код выдаёт бот.',
            ],
            en: [
              'Open @jar_v1_s in Telegram and press Start.',
              'Download the Windows app from the Download page.',
              'In the app choose sign-in by code — the bot issues the code.',
            ],
          },
          {
            kind: 'note',
            ru: 'Один аккаунт — все клиенты. Тариф, лимиты и настройки общие для Telegram, Desktop и Web. История переписки пока своя в каждом клиенте.',
            en: 'One account, every client. Plan, limits and settings are shared across Telegram, Desktop and Web. Conversation history is still per-client for now.',
          },
        ],
      },
      {
        slug: 'telegram',
        titleRu: 'Настройка Telegram',
        titleEn: 'Telegram setup',
        blocks: [
          {
            kind: 'text',
            ru: 'Бот полностью кнопочный — команды набирать не нужно. Через меню настраиваются язык, имя ассистента, модель, память, голос и тариф.',
            en: 'The bot is entirely button-driven — no commands to type. The menu covers language, assistant name, model, memory, voice and your plan.',
          },
          {
            kind: 'text',
            ru: 'Голосовые сообщения работают сразу: отправьте голосовое, и ассистент распознает речь, ответит текстом и при желании озвучит ответ.',
            en: 'Voice messages work out of the box: send one and the assistant transcribes it, answers, and can speak the answer back.',
          },
        ],
      },
      {
        slug: 'desktop',
        titleRu: 'Настройка Desktop',
        titleEn: 'Desktop setup',
        blocks: [
          {
            kind: 'text',
            ru: 'Приложение работает в двух режимах. Локальный — движок запускается на вашем компьютере, нужен свой ключ или локальная модель. Удалённый — ассистент работает через сервер, а действия на ПК выполняются здесь.',
            en: 'The app runs in two modes. Local — the engine runs on your computer and needs your own key or a local model. Remote — the assistant runs through the server while PC actions still happen here.',
          },
          {
            kind: 'note',
            ru: 'Доступ к файлам, терминалу и управлению компьютером выключен по умолчанию. Включается в разделе «Возможности» по одному, с выбором: запретить, спрашивать каждый раз или разрешить.',
            en: 'Access to files, the shell and PC control is off by default. Enable them one at a time under Capabilities, choosing deny, ask each time, or allow.',
          },
        ],
      },
    ],
  },
  {
    titleRu: 'Возможности',
    titleEn: 'Capabilities',
    articles: [
      {
        slug: 'memory',
        titleRu: 'Память',
        titleEn: 'Memory',
        blocks: [
          {
            kind: 'text',
            ru: 'Ассистент хранит историю разговоров и отдельно — устойчивые факты о вас, которые выделяет из переписки. При новом вопросе он находит подходящее по смыслу, а не по совпадению слов.',
            en: 'The assistant stores conversation history and, separately, durable facts about you distilled from it. On a new question it retrieves what is relevant by meaning, not by word match.',
          },
          {
            kind: 'text',
            ru: 'Память можно посмотреть и почистить: в приложении есть раздел, где записи видны списком, ищутся и удаляются по одной.',
            en: 'Memory is inspectable: the app has a screen listing entries, with search and per-entry deletion.',
          },
          {
            kind: 'note',
            ru: 'Пароли, токены и номера карт вычищаются автоматически до того, как что-либо будет сохранено.',
            en: 'Passwords, tokens and card numbers are stripped automatically before anything is written.',
          },
        ],
      },
      {
        slug: 'agents',
        titleRu: 'Агенты',
        titleEn: 'Agents',
        blocks: [
          {
            kind: 'text',
            ru: 'Для многошаговой задачи ассистент запускает под-агента: тот сам планирует шаги, вызывает нужные инструменты и возвращает результат. Число шагов ограничено, чтобы агент не работал бесконечно.',
            en: 'For a multi-step task the assistant runs a sub-agent: it plans the steps, calls the tools it needs and returns the result. Step count is capped so it cannot run forever.',
          },
        ],
      },
      {
        slug: 'actions',
        titleRu: 'Действия на компьютере',
        titleEn: 'PC actions',
        blocks: [
          {
            kind: 'text',
            ru: 'Ассистент умеет открывать сайты и приложения, печатать текст, нажимать клавиши и делать скриншоты. Команды нигде не прописаны списком — модель сама понимает намерение и вызывает нужный инструмент.',
            en: 'The assistant can open sites and apps, type text, press keys and take screenshots. There is no hardcoded command list — the model recognises the intent and calls the matching tool.',
          },
          {
            kind: 'text',
            ru: 'Демонстрация экрана включается голосом или текстом. Пока она включена, к каждому вашему сообщению прикладывается свежий снимок экрана, и ассистент видит, что открыто.',
            en: 'Screen sharing is turned on by voice or text. While it is on, a fresh screenshot accompanies each of your messages so the assistant can see what is open.',
          },
        ],
      },
      {
        slug: 'automation',
        titleRu: 'Автоматизация',
        titleEn: 'Automation',
        blocks: [
          {
            kind: 'text',
            ru: 'Напоминания и повторяющиеся задачи создаются обычной фразой: скажите, что и когда нужно сделать. Ассистент выполнит задачу в срок и пришлёт результат.',
            en: 'Reminders and recurring tasks are created in plain language: say what to do and when. The assistant runs the task on time and sends the result.',
          },
          {
            kind: 'note',
            ru: 'Проактивные сообщения — когда ассистент пишет первым, заметив что-то, — включаются вами и по умолчанию выключены.',
            en: 'Proactive messages — the assistant writing first because it noticed something — are opt-in and off by default.',
          },
        ],
      },
    ],
  },
  {
    titleRu: 'Продвинутое',
    titleEn: 'Advanced',
    articles: [
      {
        slug: 'models',
        titleRu: 'Модели и свой ключ',
        titleEn: 'Models and your own key',
        blocks: [
          {
            kind: 'text',
            ru: 'Поддерживаются Anthropic, OpenAI, OpenRouter и локальные модели через Ollama, LM Studio, vLLM или llama.cpp. Можно подключить собственный ключ — тогда запросы идут напрямую к провайдеру.',
            en: 'Anthropic, OpenAI, OpenRouter and local models via Ollama, LM Studio, vLLM or llama.cpp are supported. You can plug in your own key, and requests then go straight to that provider.',
          },
          {
            kind: 'text',
            ru: 'С локальной моделью ассистент работает полностью на вашей машине — данные никуда не уходят.',
            en: 'With a local model the assistant runs entirely on your machine — nothing leaves it.',
          },
        ],
      },
      {
        slug: 'mcp',
        titleRu: 'MCP-серверы',
        titleEn: 'MCP servers',
        blocks: [
          {
            kind: 'text',
            ru: 'K.E.R. понимает Model Context Protocol: инструменты любого MCP-сервера становятся обычными навыками ассистента. Сервер добавляется в настройках и подключается на лету.',
            en: 'K.E.R. speaks the Model Context Protocol: any MCP server’s tools become ordinary assistant skills. A server is added in settings and connects at runtime.',
          },
        ],
      },
      {
        slug: 'self-host',
        titleRu: 'Запуск у себя',
        titleEn: 'Self-hosting',
        blocks: [
          {
            kind: 'text',
            ru: 'Исходный код открыт под лицензией MIT. Проект поднимается через Docker Compose; нужен домен и ключ провайдера (или локальная модель).',
            en: 'The source is open under MIT. The project runs via Docker Compose; you need a domain and a provider key (or a local model).',
          },
          {
            kind: 'code',
            ru: 'git clone https://github.com/nomadnairi/K.E.R.git\ncd K.E.R\ncp .env.example .env\ndocker compose up -d --build',
            en: 'git clone https://github.com/nomadnairi/K.E.R.git\ncd K.E.R\ncp .env.example .env\ndocker compose up -d --build',
          },
        ],
      },
      {
        slug: 'security',
        titleRu: 'Безопасность',
        titleEn: 'Security',
        blocks: [
          {
            kind: 'text',
            ru: 'Опасные возможности выключены по умолчанию и включаются по одной. Каждое обращение к возможности пишется в журнал. Пароли хранятся только в виде хэша, секреты вычищаются из памяти.',
            en: 'Dangerous capabilities are off by default and enabled one at a time. Every use is written to an audit log. Passwords are stored only as hashes and secrets are stripped from memory.',
          },
          {
            kind: 'note',
            ru: 'Сквозное шифрование (E2E) находится в разработке и пока не заявляется как работающее.',
            en: 'End-to-end encryption is in development and is not claimed as working yet.',
          },
        ],
      },
    ],
  },
] as const;

export const ALL_ARTICLES: readonly DocArticle[] = DOCS.flatMap((s) => s.articles);
