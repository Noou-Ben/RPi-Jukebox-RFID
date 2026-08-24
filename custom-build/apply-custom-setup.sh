#!/usr/bin/env bash
# Applies this build's hardware-specific configuration on top of a fresh,
# already-completed v3 Jukebox install.
#
# Run this AFTER the standard install finishes and AFTER the RC522, rotary
# encoder, and prev/next buttons are wired per custom-build/README.md - not
# before, and not as part of the main installer.
#
# Usage (from the repo root on the Pi, e.g. ~/RPi-Jukebox-RFID):
#   ./custom-build/apply-custom-setup.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETTINGS_DIR="${REPO_ROOT}/shared/settings"
MPD_CONF="${HOME}/.config/mpd/mpd.conf"
BOOT_CONFIG="/boot/firmware/config.txt"

echo "== Applying custom build config from ${REPO_ROOT}/custom-build =="

if [[ ! -d "${SETTINGS_DIR}" ]]; then
    echo "ERROR: ${SETTINGS_DIR} not found. Run this after the standard install completes." >&2
    exit 1
fi

# --- 1. Enable SPI (needed for the RC522) ---------------------------------
echo "-- Enabling SPI in ${BOOT_CONFIG}"
if grep -q '^dtparam=spi=on' "${BOOT_CONFIG}" 2>/dev/null; then
    echo "   already enabled"
elif grep -q '^#dtparam=spi=on' "${BOOT_CONFIG}" 2>/dev/null; then
    sudo sed -i 's/^#dtparam=spi=on/dtparam=spi=on/' "${BOOT_CONFIG}"
    echo "   enabled (reboot required)"
else
    echo "dtparam=spi=on" | sudo tee -a "${BOOT_CONFIG}" >/dev/null
    echo "   added (reboot required)"
fi

# --- 2. Drop in the RFID reader and GPIO input device configs -------------
echo "-- Installing rfid.yaml and gpio.yaml"
cp "${REPO_ROOT}/custom-build/configs/rfid.yaml" "${SETTINGS_DIR}/rfid.yaml"
cp "${REPO_ROOT}/custom-build/configs/gpio.yaml" "${SETTINGS_DIR}/gpio.yaml"

# --- 3. Patch jukebox.yaml: enable gpioz, enable the volume bridge --------
echo "-- Patching jukebox.yaml (gpioz.enable, volume.bridge_to_player_volume)"
python3 - "${SETTINGS_DIR}/jukebox.yaml" << 'PYEOF'
import sys
import ruamel.yaml

path = sys.argv[1]
yaml = ruamel.yaml.YAML()
yaml.preserve_quotes = True
with open(path) as f:
    data = yaml.load(f)

data.setdefault('gpioz', {})
data['gpioz']['enable'] = True
data['gpioz'].setdefault('config_file', '../../shared/settings/gpio.yaml')

data.setdefault('volume', {})
data['volume']['bridge_to_player_volume'] = True

with open(path, 'w') as f:
    yaml.dump(data, f)

print("   jukebox.yaml patched")
PYEOF

# --- 4. Patch mpd.conf: type "pulse" + mixer_type "software" --------------
# Keeping type "pulse" (not switching to raw ALSA) preserves PipeWire's mute
# and output-switching behaviour. mixer_type "software" is required because
# this specific DAC accepts PipeWire volume changes but never actually
# applies any gain - see custom-build/README.md for the full story.
echo "-- Patching mpd.conf audio_output mixer_type"
if [[ ! -f "${MPD_CONF}" ]]; then
    echo "ERROR: ${MPD_CONF} not found. Has MPD been set up yet?" >&2
    exit 1
fi
python3 - "${MPD_CONF}" << 'PYEOF'
import re
import sys

path = sys.argv[1]
with open(path) as f:
    content = f.read()

pattern = re.compile(
    r'(audio_output\s*\{\s*\n\s*type\s+"pulse"\s*\n\s*name\s+"[^"]*"\s*\n\s*mixer_type\s+)"none"',
)
new_content, count = pattern.subn(r'\1"software"', content, count=1)
if count == 0:
    if 'mixer_type      "software"' in content or "mixer_type\t\"software\"" in content:
        print("   already set to software, nothing to do")
        sys.exit(0)
    print(
        "ERROR: could not find the expected 'type \"pulse\" / mixer_type \"none\"' "
        "block in mpd.conf. It may already be customised - check it by hand.",
        file=sys.stderr,
    )
    sys.exit(1)

with open(path, 'w') as f:
    f.write(new_content)
print("   mpd.conf patched")
PYEOF

echo ""
echo "== Done. Reboot for the SPI change to take effect: sudo reboot =="
