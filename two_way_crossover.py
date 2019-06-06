#!/usr/bin/env python3
from enum import Enum
import threading
import time
import gi
import os
import json
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst

Gst.init(None)
parameter_file = 'two_way_crossover.json'
current_parameters = {}


class Configuration(Enum):
    LEFT = 0
    RIGHT = 1
    MONO = 2
    STEREO = 3


def construct_pipeline(configuration):
    """
    Launch the gstreamer pipeline according to the choosen configuration (from configuration file).
    For a bass lift only the low 3 bands of the standard 10 band equalizer are exposed here.
    This should probably have been a 6 dB/oct shelving filter or something equally exotic
    but that will be another day.
    Also note that there are a total of 3 volume controls per channel to aid when playing
    around, they should probably just be removed.
    """

    # Alsa device selection
    # The first entry is used the single output modes: left only, right only and mono.
    # The the second entry is the second output alsa device used when running in stereo mode.
    alsa_devices = ['hw:0', 'hw:1']

    # Input Alsa device is always the first entry in the alsa_devices above.
    input = (f'alsasrc device={alsa_devices[0]} ! audioconvert ! audio/x-raw,format=F32LE,channels=2 ! '
             f'queue ! ')

    if configuration in (Configuration.LEFT, Configuration.RIGHT):
        # pick which of the two input channels to play (src_0 or src_1) if part of a stereo setup
        channel = f'deinterleave name=d d.src_{configuration.value} ! tee name=t{configuration.value} '
        paths = [configuration.value]
        alsa_devices = [alsa_devices[0]] * 2

    elif configuration == Configuration.MONO:
        # stereo signal mixed to mono
        channel = 'audioconvert ! audio/x-raw,channels=1 ! deinterleave name=d d.src_0 ! tee name=t0 '
        paths = [Configuration.LEFT.value]

    else:
        # stereo
        channel = 'deinterleave name=d d.src_0 ! tee name=t0 d.src_1 ! tee name=t1 '
        paths = [Configuration.LEFT.value, Configuration.RIGHT.value]

    launch = input + channel

    for path in paths:

        launch += (f'interleave name=i{path} ! capssetter caps = audio/x-raw,channels=2,channel-mask=0x3 ! '
                   f'audioconvert ! audioresample ! queue ! '
                   f'volume name=master_vol{path} volume=0.01 ! '
                   f'alsasink device={alsa_devices[path]} sync=true buffer-time=10 ')

        launch += (f't{path}.src_0 ! queue ! '
                   f'equalizer-10bands name=equalizer{path} band0=0.0 band1=6.0 band2=0.0 ! ' 
                   f'audiocheblimit name=low_xover{path} poles=8 mode=low-pass cutoff=2000.0 ! '
                   f'volume name=low_vol{path} volume=1.0 ! i{path}.sink_0 ')

        launch += (f't{path}.src_1 ! queue ! audiocheblimit name=high_xover{path} poles=8 mode=high-pass cutoff=2000.0 ! '
                   f'volume name=high_vol{path} volume=1.0 ! i{path}.sink_1 ')

    # The printed launch line can be used directly with the gst-launch tool for testing on the command line
    # print(launch)

    pipeline = Gst.parse_launch(launch)

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

parameter_file_watcher_thread = threading.Thread(target=parameter_file_watcher)
parameter_file_watcher_thread.run()

GLib.MainLoop().run()
