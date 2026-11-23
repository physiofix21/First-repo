# Машината 5П · AI реклами за PhysioFix

Система, която от една команда — **„направи партидата“** — прави рекламите за Meta и ги качва **на пауза**:

- **12 банера** с кирилица, буква по буква (1:1, 4:5, 9:16), в цветовете и шрифтовете на PhysioFix
- **3 видеа 9:16** от хук + тяло + призив, с глас и субтитри, без камера
- **текстове 5/5/5**, проверени за здравните правила на Meta и без цени
- **1 ABO кампания · 3 ad set-а · 15 реклами** в Ads Manager, на пауза, с линк
- **отчет в ден 3, 7 и 14**: спри / остави / умножи, с числото, и „вълна 2“ за победителя

Ти решаваш, машината изпълнява: спира за „да“ преди парите (Стоп А) и преди качването (Стоп Б). Пускаш ти.

**Започни от [START.md](START.md).**

```bash
cp .env.example .env          # ключовете за KIE.AI и Meta
./mashina doktor              # проверка
./mashina                     # всички команди
python3 -m unittest discover -s tests
```

Инструменти: Claude Code (или Codex) · KIE.AI (Nano Banana, Veo 3, ElevenLabs) · Meta Marketing API · Python 3.11+ с Pillow · ffmpeg · Google Sheets/Excel. Шрифтове: Montserrat и Manrope (SIL OFL, в `paket/assets/fonts/`).
