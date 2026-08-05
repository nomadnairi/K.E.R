/**
 * Russian copy — the source of truth for the dictionary's shape.
 *
 * `en.ts` is typed against this object, so a missing or misspelled key is a
 * build error rather than a placeholder string shipped to production.
 *
 * Content rule (from the brief): only claims that can be verified against the
 * code or ROADMAP.md. No user counts, no uptime figures, no invented
 * integrations.
 */
export const ru = {
  nav: {
    product: 'Продукт',
    features: 'Возможности',
    pricing: 'Тарифы',
    download: 'Скачать',
    docs: 'Документация',
    security: 'Безопасность',
    start: 'Начать',
  },

  hero: {
    eyebrow: 'PERSONAL AI CORE',
    title: 'K.E.R.',
    subtitle: 'ВАШ ЛИЧНЫЙ AI-АССИСТЕНТ',
    tagline: 'Понимает. Помнит. Действует.',
    description:
      'K.E.R. — это не просто чат. Это ваш персональный AI Core, который ' +
      'помогает в работе, управляет устройствами и автоматизирует рутину.',
    ctaPrimary: 'Начать в Telegram',
    ctaSecondary: 'Скачать Desktop',
    pills: [
      'Память без ограничений',
      'Агенты и инструменты',
      'Доступ ко всем устройствам',
      'Локально или в облаке',
      'Полный контроль',
    ],
    // Verifiable facts only — replaces the mockup's invented user/uptime stats.
    factsLabel: 'ЧТО ЭТО ЗНАЧИТ',
    facts: [
      { value: 'MIT', label: 'открытый исходный код' },
      { value: '4', label: 'провайдера LLM, включая локальные' },
      { value: '3', label: 'клиента: Telegram, Desktop, Web' },
      { value: 'RU / EN / UZ', label: 'языка ассистента' },
    ],
  },

  ecosystem: {
    title: 'Одно ядро. Любой клиент.',
    // Только то, что действительно общее сегодня: аккаунт, тариф, настройки.
    // Память у бота и у desktop/веб пока лежит в разных пространствах имён,
    // так что «одна память» была бы обещанием, которое нечем подтвердить.
    subtitle: 'Один аккаунт, один тариф, одни настройки.',
    core: 'AI CORE',
    coreCaption: 'память · агенты · инструменты',
    clients: {
      telegram: { name: 'Telegram', caption: 'Самый быстрый старт' },
      desktop: { name: 'Desktop', caption: 'Полный доступ к ПК' },
      web: { name: 'Web', caption: 'Из любого браузера' },
    },
    soon: 'Скоро',
  },

  features: {
    title: 'Возможности K.E.R.',
    subtitle: 'Один ассистент. Безграничные возможности.',
    all: 'Все возможности',
    items: {
      memory: {
        name: 'Память',
        text: 'Запоминает важное и контекст разговоров',
      },
      agents: {
        name: 'Агенты',
        text: 'Выполняют задачи через под-агентов',
      },
      actions: {
        name: 'Действия',
        text: 'Управляет ПК, файлами и приложениями',
      },
      automation: {
        name: 'Автоматизация',
        text: 'Расписания, сценарии и триггеры',
      },
      integrations: {
        name: 'Интеграции',
        // Real set: Home Assistant, Open-Meteo, HTTP, Telegram channel + MCP.
        text: 'Умный дом, погода, HTTP и любой MCP-сервер',
      },
      voice: {
        name: 'Голос',
        text: 'Естественное общение и озвучка ответов',
      },
      security: {
        name: 'Безопасность',
        text: 'Локально или в облаке. Ваши данные под защитой',
      },
      multiplatform: {
        name: 'Мультиплатформа',
        text: 'Telegram, Desktop, Web — один аккаунт',
      },
      opensource: {
        name: 'Открытый код',
        text: 'Прозрачность и свобода. MIT License',
      },
    },
  },

  memory: {
    title: 'Память, которая работает на вас',
    subtitle: 'Не история переписки, а знание о вас.',
    points: [
      'Хранит контекст между сессиями и перезапусками',
      'Выделяет из разговоров устойчивые факты',
      'Находит нужное по смыслу, а не по совпадению слов',
      'Пароли, токены и номера карт вычищаются до сохранения',
    ],
    demoUser: 'Я держу бэкапы на диске D.',
    demoLater: 'через неделю',
    demoAsk: 'Куда сохранить архив проекта?',
    demoAnswer: 'На диск D — вы там держите бэкапы.',
  },

  agents: {
    title: 'Агенты',
    subtitle: 'Ассистент делит задачу на шаги и выполняет их сам.',
    steps: [
      { name: 'Задача', text: 'Вы формулируете цель обычными словами' },
      { name: 'План', text: 'Ассистент разбивает её на шаги' },
      { name: 'Инструменты', text: 'Вызывает поиск, файлы, ПК, интеграции' },
      { name: 'Результат', text: 'Возвращается с готовым ответом' },
    ],
    note: 'Число шагов ограничено, чтобы агент не работал бесконечно.',
  },

  automation: {
    title: 'Автоматизация',
    subtitle: 'Работает, пока вы заняты другим.',
    items: [
      { name: 'Напоминания', text: 'Скажите когда — напомнит в срок' },
      { name: 'Расписания', text: 'Задача повторяется сама, без вашего участия' },
      { name: 'Проактивность', text: 'Заметил нагрузку на систему — написал первым' },
    ],
    optIn: 'Проактивные сообщения включаются вами и выключены по умолчанию.',
  },

  desktop: {
    title: 'Приложение для компьютера',
    subtitle: 'Command Deck — ассистент с доступом к вашей машине.',
    points: [
      'Открывает сайты и приложения, печатает, нажимает клавиши',
      'Видит экран, когда вы включаете демонстрацию',
      'Работает и на своей модели, и через сервер',
      'Каждая опасная возможность выключена по умолчанию',
    ],
    cta: 'Скачать для Windows',
  },

  security: {
    title: 'Безопасность',
    subtitle: 'Ассистенту с доступом к ПК доверяют не на слово.',
    items: [
      {
        name: 'Выключено по умолчанию',
        text: 'Файлы, терминал и управление ПК требуют явного включения',
      },
      {
        name: 'Три состояния доступа',
        text: 'Запретить, спрашивать каждый раз или разрешить',
      },
      {
        name: 'Журнал действий',
        text: 'Каждое обращение к возможности записывается',
      },
      {
        name: 'Секреты не сохраняются',
        text: 'Пароли и токены вычищаются перед записью в память',
      },
      {
        name: 'Свой ключ, своя модель',
        text: 'BYOK или локальная модель — данные не покидают машину',
      },
      {
        name: 'Открытый код',
        text: 'Проверяйте сами: исходники под MIT на GitHub',
      },
    ],
    honest:
      'Сквозное шифрование (E2E) в разработке и пока не заявляется как ' +
      'работающее.',
  },

  pricing: {
    title: 'Тарифы',
    subtitle: 'Честные цены. Прозрачные лимиты.',
    popular: 'Популярный',
    perMonth: 'в месяц',
    free: 'Бесплатно',
    stars: 'Stars',
    note: 'Оплата через Telegram Stars · Без карты · Отмена в любой момент',
    cta: { free: 'Попробовать бесплатно', paid: 'Выбрать' },
    tiers: {
      free: { name: 'Free', caption: 'Для знакомства с K.E.R.' },
      plus: { name: 'Plus', caption: 'Для активного использования' },
      pro: { name: 'Pro', caption: 'Для профессионалов' },
    },
    limits: {
      messages: 'сообщений в день',
      messagesUnlimited: 'Неограниченно сообщений',
      // Three Russian plural forms — see i18n/plural.ts.
      integrations: ['интеграция', 'интеграции', 'интеграций'] as [
        string,
        string,
        string,
      ],
      integrationsUnlimited: 'Интеграции без ограничений',
    },
    perks: {
      memory: 'Персональная память',
      allModels: 'Все модели',
      images: 'Генерация изображений',
      api: 'Доступ к API',
      desktop: 'Действия на ПК и демонстрация экрана',
      priority: 'Приоритетная обработка',
    },
  },

  faq: {
    title: 'Вопросы',
    items: [
      {
        q: 'Чем это отличается от обычного чат-бота?',
        a: 'K.E.R. помнит вас между разговорами и выполняет действия — ' +
          'открывает приложения, работает с файлами, запускает задачи по ' +
          'расписанию. Обычный чат только отвечает.',
      },
      {
        q: 'Нужна ли банковская карта?',
        a: 'Нет. Оплата идёт через Telegram Stars, бесплатный тариф ' +
          'доступен сразу и без оплаты.',
      },
      {
        q: 'Мои данные уходят к вам на сервер?',
        a: 'Зависит от того, как вы запускаете K.E.R. Через бота — запросы ' +
          'идут через сервер. С локальной моделью или своим ключом — нет.',
      },
      {
        q: 'Ассистент правда управляет компьютером?',
        a: 'Да, но только если вы это разрешили. По умолчанию доступ к ' +
          'файлам, терминалу и управлению ПК выключен.',
      },
      {
        q: 'Один аккаунт работает во всех клиентах?',
        a: 'Да. Telegram, Desktop и Web — это входы в одно ядро: один ' +
          'аккаунт, один тариф, одни настройки. История переписки пока ' +
          'своя в каждом клиенте.',
      },
      {
        q: 'Можно запустить у себя?',
        a: 'Да, исходный код открыт под MIT. Ставится на свой сервер или ' +
          'компьютер.',
      },
    ],
  },

  download: {
    title: 'Скачать K.E.R.',
    subtitle: 'Выберите свою платформу.',
    windows: 'K.E.R. для Windows',
    installer: 'Полный установщик',
    download: 'Скачать',
    version: 'Версия',
    size: 'Размер',
    checksum: 'Проверить целостность (SHA256)',
    releaseNotes: 'Что нового',
    sourceCode: 'Исходный код',
    sourceCaption: 'GitHub Repository',
    loading: 'Загружаем данные о релизе…',
    failed: 'Не удалось получить данные о релизе. Откройте страницу релизов.',
    requirements: 'Windows 10/11, 64-bit',
    otherPlatforms: 'Другие платформы',
    linuxNote: 'Сборки нет — можно запустить из исходников',
    androidNote: 'Клиент есть в репозитории, готовой сборки нет',
  },

  roadmapPage: {
    title: 'Roadmap',
    subtitle: 'Что готово и что впереди. Без обещаний задним числом.',
    done: 'Готово',
    partial: 'Частично',
    planned: 'В планах',
    source: 'Список ведётся в ROADMAP.md в репозитории.',
  },

  changelogPage: {
    title: 'Changelog',
    subtitle: 'История релизов.',
    loading: 'Загружаем релизы…',
    failed: 'Не удалось получить релизы. Откройте страницу релизов на GitHub.',
    viewOnGithub: 'Смотреть на GitHub',
  },

  docsPage: {
    title: 'Документация',
    subtitle: 'Как начать и как настроить.',
    search: 'Поиск по документации',
    noResults: 'Ничего не найдено',
    onThisPage: 'На этой странице',
  },

  footer: {
    tagline: 'Персональный AI Core.',
    product: 'Продукт',
    resources: 'Ресурсы',
    community: 'Сообщество',
    roadmap: 'Roadmap',
    changelog: 'Changelog',
    github: 'GitHub',
    telegram: 'Telegram',
    channel: 'Канал',
    license: 'MIT License',
    rights: 'Открытый исходный код.',
  },

  common: {
    soon: 'Скоро',
    readMore: 'Читать дальше',
  },
};

/**
 * The dictionary's shape.
 *
 * Deliberately NOT `as const`: with literal types every English string would
 * be "not assignable" to its Russian counterpart. What must match between the
 * locales is the set of keys, not the text.
 */
export type Dictionary = typeof ru;
