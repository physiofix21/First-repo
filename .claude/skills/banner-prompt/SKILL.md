---
name: banner-prompt
description: "Промптовете за снимките на банерите (KIE.AI Nano Banana / Magnific): скелети по семейства — бял фон, студио, в употреба, кабинет, анатомия. Използвай, когато банер няма твоя истинска снимка."
---

# Промптове за банери

**Първо истински снимки.** Снимка от кабинета (терапевт в работа, ръце, маса, уреди) винаги бие AI. AI само когато няма.

## Как машината пише текста
`biznes.toml → [kie] tekst_v_banera`:
- **`nadpis`** (по подразбиране): AI прави **само снимката, без текст**. Машината пише заглавието с Montserrat → кирилицата е 100% вярна. В промпта **не пишеш** текст; машината добавя „No text“ сама.
- **`ai`**: текстът влиза в промпта и AI го рисува. След генериране **гледаш всеки банер буква по буква** (отваряш PNG-то) и сравняваш със `zaglavie`. Грешна буква → генерираш пак (макс. 2 пъти) → иначе превключваш този банер на `nadpis`.

## Скелетът (на английски, AI-ят го разбира най-добре)
```
[SUBJECT], [ACTION/POSE], in [PLACE].
[LIGHT], [CAMERA/LENS], [MOOD].
Composition: [where the empty space is] for headline text, 4:5 vertical.
Colors: dark green #16351F, warm orange #EB6F04 accents, cream #F6F1E8.
Photorealistic, natural skin, no text, no logos, no watermark.
```
**Празното място** е важно: за `snimka` → горната третина; за `bolka` → долната половина е панел, обектът е горе; за `mehanizam` → кадърът е широк, без хора в краищата.

## Семейства
| Семейство | Кога | Скелет |
|---|---|---|
| **Кабинет** | доверие, механизъм | `Bright modern physiotherapy room, treatment table with folded towel, resistance bands and foam roller, soft morning window light, 35mm, calm and clean, empty upper third` |
| **В употреба** | болка, ситуация | `Hands of a physiotherapist (no face) gently working on a lower back, close-up, warm side light, shallow depth of field` — **без лице на „пациент“** |
| **Ситуация** | болка | `Office chair and laptop at the end of a long workday, low warm light, empty chair, cinematic, no people` |
| **Предмет/студио** | оферта, у дома | `Portable massage table folded next to a front door, cream background, studio light, minimal` |
| **Анатомия** | механизъм, мит/факт | `Clean 3D anatomical illustration of the lumbar spine and muscles, soft orange highlight on lower back muscles, cream background, medical-illustration style` |
| **Бял фон** | доказателство | `Minimal cream background with soft paper texture and gentle shadow, lots of empty space` |

## Забранено в промпта (здравни правила + PhysioFix)
Лица на „пациенти“, болка на лицето, кръв, преди/след, рентгенови снимки с диагнози, конкретни хора от екипа (AI не прави истинските ни хора), лога на други марки.

## След генериране
Отваряш всяка снимка: ръце (6 пръста?), странни предмети, текст, който не е трябвало да има. Лоша → повтаряш с поправка в промпта.
