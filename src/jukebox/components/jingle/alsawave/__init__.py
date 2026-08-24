"""
ALSA wave jingle Service for jingle.JingleFactory
"""
import alsaaudio
import logging
import time
import wave
import os
import jukebox.cfghandler
import jukebox.plugs as plugin

logger = logging.getLogger('jb.alsaif')
cfg = jukebox.cfghandler.get_handler('jukebox')


# ---------------------------------------------------------------------------
# Jingle Service for WAVE by ALSA
# ---------------------------------------------------------------------------

@plugin.register
class AlsaWave:
    """Jingle Service for playing wave files directly from Python through ALSA"""
    fmt_lookup = {1: alsaaudio.PCM_FORMAT_U8,
                  2: alsaaudio.PCM_FORMAT_S16_LE,
                  3: alsaaudio.PCM_FORMAT_S24_3LE,
                  4: alsaaudio.PCM_FORMAT_S32_LE}

    @classmethod
    def _play_wave_core(cls, filename):
        with wave.open(filename, 'rb') as f:
            width = f.getsampwidth()
            if width not in AlsaWave.fmt_lookup:
                raise ValueError('Unsupported format')
            device_name = cfg.setndefault('alsawave', 'device', value='default')
            period_size = f.getframerate() // 8
            device = alsaaudio.PCM(channels=f.getnchannels(),
                                   rate=f.getframerate(),
                                   format=AlsaWave.fmt_lookup[width],
                                   periodsize=period_size,
                                   device=device_name)

            data = f.readframes(period_size)
            while data:
                device.write(data)
                data = f.readframes(period_size)

            # device.write() only blocks until data is accepted into ALSA's
            # ring buffer, not until it has actually reached the speaker.
            # Closing/discarding the device right after the last write() can
            # drop whatever is still buffered instead of playing it out -
            # audible as a truncated click, or total silence if none of it
            # had reached the hardware yet. Give it time to drain first.
            time.sleep(0.6)
            device.close()

    @plugin.tag
    def play(self, filename):
        """Play the wave file"""
        if os.path.exists(filename) and os.path.isfile(filename):
            logger.debug("Playing wave file")
            try:
                AlsaWave._play_wave_core(filename)
            except Exception as e:
                logger.error(f"{type(e)}: {e}")
        else:
            logger.error(f"File does not exist: '{filename}'")
            raise KeyError(f"File does not exist: '{filename}'")


class AlsaWaveBuilder:

    def __init__(self):
        """
        Builder instantiates AlsaWave during init and not during first call because
        we want AlsaWave registers as plugin function in any case if this plugin is loaded
        (and not only on first use!)
        """
        self._instance = AlsaWave(plugin_name='alsawave', plugin_register=True)

    def __call__(self, *args, **kwargs):
        # if not self._instance:
        #     self._instance = AlsaWave(plugin_name='alsawave', plugin_register=True)
        return self._instance


# ---------------------------------------------------------------------------
# Plugin Initializer / Finalizer
# ---------------------------------------------------------------------------

@plugin.initialize
def initialize():
    jingle = plugin.get('jingle')
    jingle.factory.register("wav", AlsaWaveBuilder())
