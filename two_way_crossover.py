#!/usr/bin/env python3
from enum import Enum
import threading, time, gi, os, json

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst

Gst.init(None)
parameter_file = 'two_way_crossover.json'
current_parameters = {}


class Configuration(Enum):
    LEFT = 0
    RIGHT = 1
    MONO = 2
    STEREO = 3  # two single stereo output sound cards
    STEREO_40 = 4  # single 5.1/7.1 sound card using front and rear stereo outputs


def construct_pipeline(configuration):
    """
    Launch the gstreamer pipeline according to the choosen configuration (from configuration file).
    Bass lift adjustment is made with the low 3 bands of the standard 10 band equalizer which is
    not really the way to do it properly. But it is simple and fairly intuitive to use.
    Also note that there are a total of 3 volume controls per channel to aid when playing
    around, they should probably just be removed.
    """

    # Alsa device selection
    # The primary entry is used for 'left', 'right', 'mono' and 'stereo_40' (anything but 'stereo')
    # Default Alsa device if left empty, use 'device=hw:X' to select a specific device instead
    primary = ''
    # The secondary entry is the second output alsa device used when running in 'stereo'.
    # Modify to use the correct second soundcard.
    secondary = 'device=hw:X'

    # Input Alsa device is always the primary from above.
    input = (f'alsasrc {primary} ! audioconvert ! audio/x-raw,format=F32LE,channels=2 ! '
             f'queue ! ')

    if configuration in (Configuration.LEFT, Configuration.RIGHT):
        # pick which of the two input channels to play (src_0 or src_1) if part of a stereo setup
        channel = f'deinterleave name=d d.src_{configuration.value} ! tee name=tee_0 '
        paths = [configuration.value]
        alsa_devices = [primary]
        channel_masks = [0x01]
        interleave_index = [0]

    elif configuration == Configuration.MONO:
        # stereo signal mixed to mono
        channel = 'audioconvert ! audio/x-raw,channels=1 ! deinterleave name=d d.src_0 ! tee name=tee_0 '
        paths = [Configuration.LEFT.value]
        alsa_devices = [primary]
        channel_masks = [0x01]
        interleave_index = [0]

    else:
        # 'stereo' or 'stereo_40'. 'stereo' uses two soundcards
        # and 'stereo_40' two outputs on a 5.1 soundcard.
        channel = 'deinterleave name=d d.src_0 ! tee name=tee_0 d.src_1 ! tee name=tee_1 '
        paths = [Configuration.LEFT.value, Configuration.RIGHT.value]
        if configuration == Configuration.STEREO:
            alsa_devices = [primary, secondary]
            channel_masks = [0x01, 0x01]
            interleave_index = [0, 1]
        else:
            alsa_devices = [primary, primary]
            channel_masks = [0x01, 0x10]
            interleave_index = [0, 4]

    launch = input + channel

    for path in range(len(paths)):
        interleave_element = 0

        if not path or (configuration == Configuration.STEREO):
            if path and (configuration == Configuration.STEREO):
                interleave_element = 1

            output = (f'interleave name=i{interleave_element} ! '
                      f'audioconvert ! audioresample ! queue ! '
                      f'volume name=master_vol{path} volume=0.01 ! '
                      f'alsasink name=alsasink{path} {alsa_devices[path]} ')

            launch += output

        low_ch_mask = channel_masks[path]
        high_ch_mask = low_ch_mask * 2
        low_interleave_channel = interleave_index[path]
        high_interleave_channel = low_interleave_channel + 1

        low = (f'tee_{path}.src_0 ! queue ! '
               f'equalizer-10bands name=equalizer{path} band0=0.0 band1=6.0 band2=0.0 ! '
               f'audiocheblimit name=low_xover{path} poles=8 mode=low-pass cutoff=2000.0 ! '
               f'volume name=low_vol{path} volume=1.0 ! audioconvert ! '
               f'"audio/x-raw,channels=1,channel-mask=(bitmask){low_ch_mask:#x}" ! '
               f'i{interleave_element}.sink_{low_interleave_channel} ')

        high = (f'tee_{path}.src_1 ! queue ! '
                f'audiocheblimit name=high_xover{path} poles=8 mode=high-pass cutoff=2000.0 ! '
                f'volume name=high_vol{path} volume=1.0 ! audioconvert ! '
                f'"audio/x-raw,channels=1,channel-mask=(bitmask){high_ch_mask:#x}" ! '
                f'i{interleave_element}.sink_{high_interleave_channel} ')

        launch += low + high

    # The printed launch line can be used directly with the gst-launch tool for testing on the command line
    # print(launch)

    # Python bindings refuses to run with caps in double quotes (!?)
    pipeline = Gst.parse_launch(launch.replace('"', ''))

    pipeline.set_state(Gst.State.PLAYING)

    return pipeline


def reload(parameters):
    """
    There is no sanity checking so you get what you ask for. Lookup the documentation
    for the gstreamer elements if in doubt about what sane values could look like.
    Keep master volume above 0.001 or the pipeline will stop (!?).
    """
    global current_parameters

    print('reloading parameters')
    modified = dict(parameters.items() - current_parameters.items())
    for key, value in sorted(modified.items()):
        for path in [Configuration.LEFT.value, Configuration.RIGHT.value]:
            try:
                # Common output volume
                if key == 'volume':
                    gst_pipeline.get_by_name(f'master_vol{path}').set_property('volume', value)

                # Bass crossover, equalizer and volume.
                elif key == 'low_frequency':
                    gst_pipeline.get_by_name(f'low_xover{path}').set_property('cutoff', value)
                elif key == 'low_order':
                    gst_pipeline.get_by_name(f'low_xover{path}').set_property('poles', value)
                elif key == 'low_volume':
                    gst_pipeline.get_by_name(f'low_vol{path}').set_property('volume', value)
                elif key == 'low_eq_29Hz':
                    gst_pipeline.get_by_name(f'equalizer{path}').set_property('band0', value)
                elif key == 'low_eq_59Hz':
                    gst_pipeline.get_by_name(f'equalizer{path}').set_property('band1', value)
                elif key == 'low_eq_119Hz':
                    gst_pipeline.get_by_name(f'equalizer{path}').set_property('band2', value)

                # Treble crossover and volume
                elif key == 'high_frequency':
                    gst_pipeline.get_by_name(f'high_xover{path}').set_property('cutoff', value)
                elif key == 'high_order':
                    gst_pipeline.get_by_name(f'high_xover{path}').set_property('poles', value)
                elif key == 'high_volume':
                    gst_pipeline.get_by_name(f'high_vol{path}').set_property('volume', value)
                elif key == 'buffer-time':
                    gst_pipeline.get_by_name(f'alsasink{path}').set_property('buffer-time', value)
                elif key == 'configuration':
                    if current_parameters:
                        print(' - if that was a configuration mode change then please restart the script')
                    continue
                else:
                    print(f' - error, unknown key {key}')
                    continue

                print(f' - setting {key} (channel {path}) to {value}')

            except AttributeError:
                pass

    current_parameters = parameters


def parameter_file_watcher():
    """
    Dynamically reloads the parameter file whenever its modified time changes
    """
    try:

        mtime = None
        while True:
            _ = os.path.getmtime(parameter_file)
            if _ != mtime:
                mtime = _
                with open(parameter_file) as f:
                    reload(json.loads(f.read()))
            time.sleep(1)
    except KeyboardInterrupt:
        print(' killed')
        exit(1)


with open(parameter_file) as f:
    conf = json.loads(f.read())['configuration']
    print(f'Two way crossover is starting as \'{conf}\'')
    gst_pipeline = construct_pipeline(Configuration[conf.upper()])
    error_message = gst_pipeline.get_bus().pop_filtered(Gst.MessageType.ERROR)
    if error_message:
        err, msg = error_message.parse_error()
        print(f'\nFatal error: \n{err}\n\n{msg}\n')
        exit(1)

parameter_file_watcher_thread = threading.Thread(target=parameter_file_watcher)
parameter_file_watcher_thread.run()

GLib.MainLoop().run()
