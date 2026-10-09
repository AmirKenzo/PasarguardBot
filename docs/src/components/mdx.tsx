import defaultMdxComponents from 'fumadocs-ui/mdx';
import type { MDXComponents } from 'mdx/types';
import { Step, Steps } from 'fumadocs-ui/components/steps';
import { Tab, Tabs } from 'fumadocs-ui/components/tabs';
import { Accordion, Accordions } from 'fumadocs-ui/components/accordion';
import { File, Files, Folder } from 'fumadocs-ui/components/files';
import { DonateGrid, DonateWallet } from '@/components/donate-cards';
import { CliPanel, CliPrompt } from '@/components/cli-panel';
import {
  TelegramGallery,
  TelegramPhone,
  TgBubble,
  TgBtn,
  TgKeyboard,
  TgRow,
} from '@/components/telegram-preview';
import { ZoomImage } from '@/components/zoom-image';
import { WebhookSettingsImage } from '@/components/webhook-settings-image';

export function getMDXComponents(components?: MDXComponents) {
  return {
    ...defaultMdxComponents,
    Step,
    Steps,
    Tab,
    Tabs,
    Accordion,
    Accordions,
    File,
    Files,
    Folder,
    DonateGrid,
    DonateWallet,
    CliPanel,
    CliPrompt,
    TelegramGallery,
    TelegramPhone,
    TgBubble,
    TgBtn,
    TgKeyboard,
    TgRow,
    ZoomImage,
    WebhookSettingsImage,
    ...components,
  } satisfies MDXComponents;
}

export const useMDXComponents = getMDXComponents;

declare global {
  type MDXProvidedComponents = ReturnType<typeof getMDXComponents>;
}
