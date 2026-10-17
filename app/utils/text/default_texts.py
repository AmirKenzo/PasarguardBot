from app.i18n import DEFAULT_LANGUAGE, namespace

BOT_TEXTS_NAMESPACE = "bot_texts"

DEFAULT_BOT_TEXTS: dict[str, str] = namespace(BOT_TEXTS_NAMESPACE, DEFAULT_LANGUAGE)


def default_bot_text(key: str, lang: str | None = None) -> str | None:
    return namespace(BOT_TEXTS_NAMESPACE, lang).get(key)
