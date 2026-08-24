# Spotify

Phoniebox can play music from Spotify (a **Spotify Premium account is required**) by
acting as a [Spotify Connect](https://www.spotify.com/connect/) speaker, using the
open-source [go-librespot](https://github.com/devgianlu/go-librespot) client.

Unlike v2's Mopidy-based "+Spotify Edition", this does **not** require a Spotify
Developer app registration, and your Spotify account password is never entered into or
stored by the Jukebox.

> [!NOTE]
> This is a best-effort, unverified-on-hardware first implementation. See
> `documentation/developers/status.md` for exactly what is and isn't implemented yet.

## How to connect

1. Enable Spotify support, either during installation (you will be asked) or later from
   **Settings → Spotify** in the Web App.
2. Open the Spotify app on your phone, tablet, or computer and start playing anything.
3. Tap the "Devices available" / Spotify Connect icon and select your Phoniebox
   (shown under the device name configured in `jukebox.yaml`, default `Phoniebox`) from
   the list, exactly like you would select a Chromecast or Sonos speaker.

Playback is primarily controlled from whichever app initiated the Spotify Connect
session. Basic transport actions triggered from the Jukebox itself (play/pause/skip via
RFID cards, physical buttons, or the Web App) are forwarded to the active Spotify
session, but there is currently no way to *start* a specific playlist or track from an
RFID card - that would require the Spotify Web API (OAuth), which is not implemented.

## Configuration

Relevant `jukebox.yaml` keys, under the `spotify:` section:

``` yaml
spotify:
  enable: false           # Off by default; can also be toggled live from the Web App
  device_name: Phoniebox  # Name shown in the Spotify app
  binary_path: ../../shared/spotify/bin/go-librespot
  config_dir: ../../shared/spotify
  api_host: 127.0.0.1
  api_port: 3678
  audio_backend: pulseaudio
  credentials_type: zeroconf   # No credentials stored; pair from the Spotify app
  persist_credentials: false   # Set true to stay paired across restarts
```

## Installing go-librespot manually

The installer downloads a prebuilt `go-librespot` binary for your architecture when you
opt into Spotify support (see `installation/routines/setup_spotify.sh`). If you need to
(re)install it manually, download the release matching your architecture from
<https://github.com/devgianlu/go-librespot/releases/latest> and place the extracted
`go-librespot` binary at the path configured in `spotify.binary_path` (default:
`shared/spotify/bin/go-librespot`), then make sure it is executable.

## Troubleshooting

Check **Settings → Spotify** in the Web App for the current connection status
(process running / session active / last error), or query it directly:

``` bash
./run_rpc_tool.sh -c spotify.ctrl.get_connection_status
```

If `process_running` is `false`, check that the `go-librespot` binary exists and is
executable at the configured `binary_path`.
