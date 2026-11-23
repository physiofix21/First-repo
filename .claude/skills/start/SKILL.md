---
name: start
description: "Настройката на машината: ключове за KIE.AI и Meta, .env, biznes.toml, `./mashina doktor` до „Всичко е наред“. Използвай при първо пускане или когато doktor показва ✗."
---

# Старт · настройката

Води човека **една стъпка наведнъж**. След всяка пускаш `./mashina doktor` и казваш какво остава.

## 1. Инструменти
- Python 3.11+, `pip install pillow`, ffmpeg (`brew install ffmpeg` / `winget install ffmpeg` / `apt install ffmpeg`).
- `./mashina doktor --bez-mrezha` → трябва ✓ на инструментите и шрифтовете.

## 2. Ключовете (само в `.env`)
1. `cp .env.example .env` (Windows: копирай файла ръчно).
2. **KIE.AI — само ако човекът го иска** (платено, $10). По подразбиране машината е в безплатен режим (`[kie] vkluchen = false`): пропусни тази стъпка.
3. **Meta** (най-трудната стъпка, води го бавно):
   - business.facebook.com → Настройки → Потребители → **Системни потребители** → Добави (админ).
   - „Присвои активи“: рекламният акаунт (пълен контрол) и страницата на PhysioFix.
   - „Генерирай токен“ → приложение (ако няма: developers.facebook.com → Create App → Business) → права: `ads_management`, `ads_read`, `business_management`, `pages_read_engagement`, `pages_manage_ads`, `pages_show_list`. Срок: без изтичане.
   - `META_ACCESS_TOKEN=` токенът · `META_AD_ACCOUNT_ID=act_<номер>` (Ads Manager → горе вляво) · `META_PAGE_ID=` (страницата → Информация → ID).
   - По желание `META_IG_USER_ID` (Instagram акаунтът в Business настройките), за да се показва като PhysioFix в Instagram.
4. **Никога** не искай ключа в чата. Ако го постави там → „Смени го (генерирай нов) и го сложи само в .env“.

## 3. Бизнесът: `biznes.toml`
- `[ikonomika]`: питай за 3 числа, като ги вземеш от таблиците (лист „Плащания“ и „проследяване“), ако имаш достъп:
  1. среден приход от нов пациент за 60 дни;
  2. % съобщения → записан час;
  3. % записани, които идват.
  После `popalneno = true` и `./mashina ikonomika` → таванът на съобщение.
- `[meta] shirina/dalzhina`: точните координати на кабинета (Google Maps → десен клик върху адреса).
- `[dokazatelstva]`: актуалният брой Google отзиви.

## 4. Проверката
`./mashina doktor` → „Всичко е наред.“ Тогава: „Готови сме. Кажи „направи партидата“.“
