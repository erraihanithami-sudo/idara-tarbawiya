#!/usr/bin/env bash
# ينزّل خط IBM Plex Sans Arabic (رخصة SIL OFL) عند البناء. التطبيق يعمل بدونه بخطوط Windows.
set -e
d="idara/resources/fonts"
mkdir -p "$d"
base="https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexsansarabic"
for f in IBMPlexSansArabic-Regular.ttf IBMPlexSansArabic-SemiBold.ttf OFL.txt; do
  curl -sSfL -o "$d/$f" "$base/$f" || echo "تعذر تنزيل $f (سيُستعمل خط Windows)"
done
ls -la "$d"

# خطا المظهر المغربي (رخصة SIL OFL): Tajawal للواجهة و Amiri للعناوين
for pair in "tajawal/Tajawal-Regular.ttf" "tajawal/Tajawal-Medium.ttf" "tajawal/Tajawal-Bold.ttf" \
            "amiri/Amiri-Regular.ttf" "amiri/Amiri-Bold.ttf"; do
  f="${pair##*/}"
  curl -sSfL -o "$d/$f" "https://raw.githubusercontent.com/google/fonts/main/ofl/$pair" || echo "تعذر تنزيل $f"
done
curl -sSfL -o "$d/OFL-Tajawal.txt" "https://raw.githubusercontent.com/google/fonts/main/ofl/tajawal/OFL.txt" || true
curl -sSfL -o "$d/OFL-Amiri.txt" "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/OFL.txt" || true
ls -la "$d"
