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
