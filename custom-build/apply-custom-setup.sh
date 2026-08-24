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

# --- 1. Enable the Speaker Bonnet's I2S sound driver -----------------------
# Not part of the Jukebox software itself - this is the kernel-level overlay
# Adafruit's own setup calls for. Needs a reboot to take effect, same as SPI
# below, so both changes share the single reboot at the end of this script.
echo "-- Enabling the Speaker Bonnet's I2S driver in ${BOOT_CONFIG}"
if grep -q '^dtoverlay=googlevoicehat-soundcard' "${BOOT_CONFIG}" 2>/dev/null; then
    echo "   already enabled"
else
    echo "dtoverlay=googlevoicehat-soundcard" | sudo tee -a "${BOOT_CONFIG}" >/dev/null
    echo "   added (reboot required)"
fi

# --- 2. Enable SPI (needed for the RC522) ----------------------------------
# Uses the same non-interactive raspi-config call the RC522 reader module's
# own setup.inc.sh uses, rather than editing config.txt by hand, so this
# keeps working even if a future OS release changes exactly how SPI gets
# turned on.
echo "-- Enabling SPI"
sudo raspi-config nonint do_spi 0
echo "   done (reboot required if this was the first time)"

# --- 3. Install the RC522's Python dependency ------------------------------
# The reader module's own requirements.txt pins a specific pi-rc522-gpiozero
# commit (this is what actually provides the 'pirc522' package) - install
# from that file directly rather than hardcoding the package here, so this
# stays in sync automatically if the project ever changes it.
echo "-- Installing RC522 Python dependencies"
"${REPO_ROOT}/.venv/bin/pip" install --upgrade --force-reinstall -q \
    -r "${REPO_ROOT}/src/jukebox/components/rfid/hardware/rc522_spi/requirements.txt"
echo "   done"

# --- 4. Drop in the RFID reader and GPIO input device configs -------------
echo "-- Installing rfid.yaml and gpio.yaml"
cp "${REPO_ROOT}/custom-build/configs/rfid.yaml" "${SETTINGS_DIR}/rfid.yaml"
cp "${REPO_ROOT}/custom-build/configs/gpio.yaml" "${SETTINGS_DIR}/gpio.yaml"

# --- 5. Patch jukebox.yaml: enable gpioz, enable the volume bridge --------
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
data['gpioz']['config_file'] = '../../shared/settings/gpio.yaml'

data.setdefault('volume', {})
data['volume']['bridge_to_player_volume'] = True

with open(path, 'w') as f:
    yaml.dump(data, f)

print("   jukebox.yaml patched")
PYEOF

# --- 6. Patch mpd.conf: type "pulse" + mixer_type "software" --------------
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
echo "== Done. Rebooting in 10s to activate the sound driver and SPI (Ctrl+C to cancel) =="
sleep 10
sudo reboot
