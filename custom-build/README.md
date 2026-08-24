# Custom build recipe

Everything needed to build another one of these exactly, without re-discovering
the same hardware/software gotchas from scratch. See also the rendered build
guide (with wiring diagram) published as an Artifact - ask Claude for the link
if you don't have it.

## Bill of materials

- Raspberry Pi Zero 2 W
- Adafruit I2S 3W Stereo Speaker Bonnet (product 3346)
- RFID-RC522 module (SPI, 13.56MHz), with 13.56MHz Mifare-compatible cards/fobs
  - **Not** a 125kHz "ID" reader, and not one of the "reader/writer/copier"
    duplicator gadgets sold on Amazon under near-identical listings - those are
    a completely different, incompatible product despite looking the same in
    photos. Look for a plain "reader" in the title, ideally one that mentions
    Linux/Raspberry Pi in reviews.
- 5-pin rotary encoder (KY-040 style: GND, +, SW, DT, CLK)
- 2x momentary push-button switches (prev/next)
- Female-to-female jumper wires (for anything not soldered directly)
- A speaker (4-8 ohm, wired into the Bonnet's terminal blocks)

Not needed, despite looking necessary at first: a GPIO stacking/extender
board. The Speaker Bonnet has every GPIO pin broken out as its own labelled
solder hole on its top surface (see photo/diagram), so the RC522, encoder,
and buttons all wire directly into those holes with the Bonnet plugged
straight onto the Pi as normal - no stacking header in the signal path.

## Assembly

1. Solder individual male header pins into the Bonnet's labelled breakout
   holes for every signal below (snap single pins off a header strip - the
   holes aren't evenly spaced as one continuous row, so individual pins are
   easier than a multi-pin block).
2. Wire the RC522, encoder, and buttons to those pins per the tables below.
3. Plug the Bonnet directly onto the Pi's 40-pin GPIO header as normal.

### Power cluster

3.3V and GND are **not** part of the labelled signal row above - they're a
separate group elsewhere on the Bonnet, with three holes each:

| Power pin | Goes to |
|---|---|
| 3V #1 | RC522 |
| 3V #2 | Rotary encoder |
| 3V #3 | *(spare)* |
| GND #1 | RC522 |
| GND #2 | Rotary encoder |
| GND #3 | Both buttons, via a small splitter cable (two wires into one hole) |

Three dedicated holes each means RC522 and the encoder don't need to share
or piggyback a wire - each gets its own. Only the two buttons, which don't
draw power and just need a path to ground, share a single GND hole between
them.

### RC522 (SPI)

| RC522 pin | Bonnet hole | Note |
|---|---|---|
| 3.3V | `3V #1` | see power cluster above |
| GND | `GND #1` | see power cluster above |
| SCK | `CLK` | RC522 calls it SCK, the Bonnet labels it CLK - same signal |
| MOSI | `MOSI` | |
| MISO | `MISO` | |
| SDA | `CE0` | **Not** the Bonnet's `SDA` hole - that's I2C, unrelated. The RC522's "SDA" label is a leftover from an alternate I2C mode these boards don't use; it's actually the SPI chip-select line |
| RST | *(self-jumper)* | Wire RST directly to the RC522's own 3.3V pin, on the RC522 board itself - do not run it to the Pi. See "Why pin_rst isn't wired" below |
| IRQ | *(unconnected)* | Left unwired; the config runs in polling mode instead |

### Rotary encoder

| Encoder pin | Bonnet hole |
|---|---|
| CLK | `5` |
| DT | `6` |
| SW | `13` |
| GND | `GND #2` |
| + | `3V #2` |

If clockwise/counter-clockwise ever comes out backwards, swap the CLK/DT
wires (or swap `a`/`b` in `configs/gpio.yaml`) - harmless either way.

### Buttons

| Button | Bonnet hole |
|---|---|
| Prev (one leg) | `12` |
| Next (one leg) | `20` |
| Both (other leg) | `GND #3`, via splitter |

**Do not use GPIO16** for anything - it's the Bonnet's own amplifier
shutdown/enable line (`sdmode` in the kernel's GPIO consumer list), driven
by the sound driver itself. Wiring anything else there will either fail
outright ("GPIO busy") or interfere with the amp being enabled.

## Software setup

1. Flash Raspberry Pi OS Lite as usual (enable SSH + WiFi in the Imager's
   customisation step).
2. Install:
   ```bash
   cd; GIT_USER='Noou-Ben' GIT_BRANCH='release/v3-custom' bash <(wget -qO- https://raw.githubusercontent.com/MiczFlor/RPi-Jukebox-RFID/future3/develop/installation/install-jukebox.sh)
   ```
   (If the installer complains about no pre-built Web App bundle: it needs a
   GitHub Actions run on `release/v3-custom` to have completed at least once
   on this fork - check the Actions tab.)
3. Once the install finishes and the Jukebox is running:
   ```bash
   cd ~/RPi-Jukebox-RFID
   ./custom-build/apply-custom-setup.sh
   sudo reboot
   ```
4. After reboot, confirm playback, volume, RFID, and all four GPIO controls
   work before closing up the enclosure.

## Why things are configured the way they are

A few settings in `configs/` look unusual on their own - here's why, so a
future "helpful cleanup" doesn't undo them:

- **`rfid.yaml`: `pin_rst: 25` even though RST isn't wired to the Pi at
  all.** The `pirc522` library crashes on `pin_rst=0` (`RuntimeError: no RST
  GPIO defined`) even though the Jukebox's own setup wizard offers 0 as "the
  way to disable it." Any real, otherwise-unused GPIO number works here -
  it's just a placeholder the library insists on, and it never gets
  physically toggled since our RST is hardware-tied high on the RC522 board
  itself.
- **`rfid.yaml`: `antenna_gain: 4`, not maxed out at 7.** Counter-intuitively,
  cranking the gain to maximum made card detection *worse* - likely receiver
  saturation at close range. 4 (the library default) is what actually gives
  reliable reads.
- **`mpd.conf`: `mixer_type "software"` instead of the default `"none"`,
  and `volume.bridge_to_player_volume: true` in `jukebox.yaml`.** This
  DAC accepts PipeWire volume changes and reports them back correctly, but
  never actually applies any gain to the audio - a real change (confirmed via
  `wpctl status`) with zero audible effect. MPD's own native volume, in
  contrast, genuinely works on this hardware. The bridge mirrors every
  volume/mute change from the WebUI's PipeWire-based control into MPD's own
  `setvol`, so the slider drives the volume that's actually doing something.
  Both settings only matter together - `mixer_type "software"` alone does
  nothing (MPD never gets told a volume to apply), and the bridge alone does
  nothing (MPD would still be ignoring its own volume with `mixer_type
  "none"`).
- **`gpio.yaml` pin choices avoid GPIO 2/3/7/8/9/10/11/18/19/21/25** - these
  are already claimed by I2C (labelled, unused but reserved), the RC522's
  SPI bus, the Bonnet's I2S audio data lines, and the RC522's RST
  placeholder, respectively.
