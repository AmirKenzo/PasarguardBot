import { useTranslation } from "react-i18next";
import { PageHeader } from "../../components/layout/PageHeader";
import { AccordionItem, Card } from "../../components/ui";

const FAQ_KEYS = [
  { title: "help.faq1Title", body: "help.faq1Body" },
  { title: "help.faq2Title", body: "help.faq2Body" },
  { title: "help.faq3Title", body: "help.faq3Body" },
  { title: "help.faq4Title", body: "help.faq4Body" },
  { title: "help.faq5Title", body: "help.faq5Body" },
  { title: "help.faq6Title", body: "help.faq6Body" },
];

export default function HelpPage() {
  const { t } = useTranslation();
  return (
    <div>
      <PageHeader title={t("help.title")} subtitle={t("help.subtitle")} back="/profile" />
      <Card className="px-4">
        {FAQ_KEYS.map((item, index) => (
          <AccordionItem key={item.title} title={t(item.title)} defaultOpen={index === 0}>
            {t(item.body)}
          </AccordionItem>
        ))}
      </Card>
    </div>
  );
}
