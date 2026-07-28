import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';
import { Bot, Megaphone, UsersRound } from 'lucide-react';
import { appName, gitConfig, telegramChannelUrl, telegramGroupUrl } from './shared';
import { botVersion } from './version';

export function baseOptions(): BaseLayoutProps {
  return {
    nav: {
      title: (
        <span className="inline-flex items-center gap-2 font-bold tracking-tight">
          <span className="inline-flex size-7 items-center justify-center rounded-lg bg-fd-primary/15 text-fd-primary">
            <Bot className="size-4" />
          </span>
          <span>{appName}</span>
          <span
            className="rounded-md border border-fd-border bg-fd-secondary/50 px-1.5 py-0.5 text-[10px] font-semibold text-fd-muted-foreground"
            dir="ltr"
          >
            v{botVersion}
          </span>
        </span>
      ),
    },
    githubUrl: `https://github.com/${gitConfig.user}/${gitConfig.repo}`,
    links: [
      {
        type: 'icon',
        url: telegramChannelUrl,
        text: 'Channel',
        label: 'Telegram channel',
        external: true,
        icon: <Megaphone className="size-5" />,
      },
      {
        type: 'icon',
        url: telegramGroupUrl,
        text: 'Group',
        label: 'Telegram group',
        external: true,
        icon: <UsersRound className="size-5" />,
      },
    ],
  };
}
