/**
 * Roadmap, mirrored from `ROADMAP.md` in the repository.
 *
 * Statuses use that file's own legend (✅ done · 🟡 partial · ⬜ planned) and
 * nothing is upgraded for the sake of the website: items marked planned there
 * are marked planned here.
 */
export type Status = 'done' | 'partial' | 'planned';

export interface RoadmapItem {
  name: string;
  nameEn: string;
  status: Status;
}

export interface RoadmapGroup {
  title: string;
  titleEn: string;
  items: RoadmapItem[];
}

export const ROADMAP: readonly RoadmapGroup[] = [
  {
    title: 'Ядро',
    titleEn: 'Core',
    items: [
      { name: 'Движок и агентный цикл', nameEn: 'Engine and agentic loop', status: 'done' },
      { name: 'Память и семантический поиск', nameEn: 'Memory and semantic recall', status: 'done' },
      { name: 'Агенты (под-агенты)', nameEn: 'Agents (sub-agents)', status: 'done' },
      { name: 'Маршрутизация моделей', nameEn: 'Model-tier routing', status: 'done' },
      { name: 'Безопасность и аудит', nameEn: 'Security and audit', status: 'done' },
    ],
  },
  {
    title: 'Клиенты',
    titleEn: 'Clients',
    items: [
      { name: 'Telegram-бот', nameEn: 'Telegram bot', status: 'done' },
      { name: 'Desktop (Windows)', nameEn: 'Desktop (Windows)', status: 'done' },
      { name: 'API и WebSocket', nameEn: 'API and WebSocket', status: 'done' },
      { name: 'Android-клиент', nameEn: 'Android client', status: 'partial' },
      { name: 'Web Dashboard', nameEn: 'Web Dashboard', status: 'partial' },
    ],
  },
  {
    title: 'Возможности',
    titleEn: 'Capabilities',
    items: [
      { name: 'Голос (STT/TTS)', nameEn: 'Voice (STT/TTS)', status: 'done' },
      { name: 'Управление ПК', nameEn: 'PC control', status: 'done' },
      { name: 'Демонстрация экрана', nameEn: 'Screen sharing', status: 'done' },
      { name: 'Генерация изображений', nameEn: 'Image generation', status: 'done' },
      { name: 'Веб-поиск', nameEn: 'Web search', status: 'done' },
      { name: 'MCP-серверы', nameEn: 'MCP servers', status: 'done' },
      { name: 'Проактивные сообщения', nameEn: 'Proactive messages', status: 'partial' },
    ],
  },
  {
    title: 'Умный дом и периферия',
    titleEn: 'Smart home and edge',
    items: [
      { name: 'Home Assistant', nameEn: 'Home Assistant', status: 'done' },
      { name: 'Ключевое слово («Hey K.E.R.»)', nameEn: 'Wake word ("Hey K.E.R.")', status: 'planned' },
      { name: 'Raspberry Pi', nameEn: 'Raspberry Pi nodes', status: 'planned' },
      { name: 'Датчики', nameEn: 'Sensors', status: 'planned' },
      { name: 'Камеры и зрение', nameEn: 'Cameras and vision', status: 'planned' },
    ],
  },
] as const;
