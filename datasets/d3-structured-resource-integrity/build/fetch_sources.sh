#!/usr/bin/env bash
# D3 source download (reproduction). Real i18n resources, Apache-2.0.
# AOSP Settings string resources for the 9 target languages + en.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$HERE/sources"
mkdir -p "$OUT"
C=7c598253ff60
BASE="https://raw.githubusercontent.com/aosp-mirror/platform_packages_apps_Settings/$C/res"
declare -A M=( [en]=values [es]=values-es [fr]=values-fr [it]=values-it \
  [ca]=values-ca [pt-PT]=values-pt-rPT [de]=values-de [nl]=values-nl \
  [pl]=values-pl [ru]=values-ru )
for lang in en es fr it ca pt-PT de nl pl ru; do
  curl -fsSL "$BASE/${M[$lang]}/strings.xml" -o "$OUT/strings.$lang.xml"
  echo "fetched $lang ($(wc -c < "$OUT/strings.$lang.xml") bytes)"
done
{ echo "COMMIT=$C"; echo "source=aosp-mirror/platform_packages_apps_Settings res/values*/strings.xml"; echo "license=Apache-2.0"; } > "$OUT/PROVENANCE.txt"
echo "done."
