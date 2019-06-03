#!/usr/bin/env python3
import threading
import time
import gi
import os
import json
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst

Gst.init(None)
current_parameters = {}


def construct_pipeline():
    """
    Launch the gstreamer pipeline for a mono two way crossover.
    For a bass lift only the low 3 bands of the standard 10 band equalizer are exposed here.
    This should probably have been a 6 dB/oct shelving filter or something equally exotic
    but that will be another day.
    Also note that there are a total of 3 volume controls to aid when playing around, just
    remove them if they are not needed.
    The alsa devices 'hw:0' are the default sound card, adjust them to the correct sound card
    if needed (run 'aplay -l' to see available sound cards).
    """
    input = ('alsasrc device=hw:0 ! audioconvert ! audio/x-raw,format=F32LE,channels=2 ! '
             'queue ! ')

    # pick which of the two input channels to play (src_0 or src_1) if part of a stereo setup
    channel = 'deinterleave name=d d.src_0 ! tee name=t0 '
    # or if a stereo signal should be mixed to mono
    # channel = 'audioconvert ! audio/x-raw,channels=1 ! deinterleave name=d d.src_0 ! tee name=t0 '

    output = ('interleave name=i0 ! capssetter caps = audio/x-raw,channels=2,channel-mask=0x3 ! '
              'audioconvert ! audioresample ! queue ! '
              'volume name=master_vol volume=0.01 ! '
              'alsasink device=hw:0 sync=true buffer-time=10 ')

    low = ('t0.src_0 ! queue ! '
           'equalizer-10bands name=equalizer band0=0.0 band1=6.0 band2=0.0 ! ' 
           'audiocheblimit name=low_xover poles=8 mode=low-pass cutoff=2000.0 ! '
           'volume name=low_vol volume=1.0 ! i0.sink_0 ')

    high = ('t0.src_1 ! queue ! audiocheblimit name=high_xover poles=8 mode=high-pass cutoff=2000.0 ! '
            'volume name=high_vol volume=1.0 ! i0.sink_1 ')

    launch = input + channel + output + low + high

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
        print(f' - setting {key} to {value}')

        # Common output volume
        if key == 'volume':
            gst_pipeline.get_by_name('master_vol').set_property('volume', value)

        # Bass crossover, equalizer and volume.
        elif key == 'low_frequency':
            gst_pipeline.get_by_name('low_xover').set_property('cutoff', value)
        elif key == 'low_order':
            gst_pipeline.get_by_name('low_xover').set_property('poles', value)
        elif key == 'low_volume':
            gst_pipeline.get_by_name('low_vol').set_property('volume', value)
        elif key == 'low_eq_29Hz':
            gst_pipeline.get_by_name('equalizer').set_property('band0', value)
        elif key == 'low_eq_59Hz':
            gst_pipeline.get_by_name('equalizer').set_property('band1', value)
        elif key == 'low_eq_119Hz':
            gst_pipeline.get_by_name('equalizer').set_property('band2', value)

        # Treble crossover and volume
        elif key == 'high_frequency':
            gst_pipeline.get_by_name('high_xover').set_property('cutoff', value)
        elif key == 'high_order':
            gst_pipeline.get_by_name('high_xover').set_property('poles', value)
        elif key == 'high_volume':
            gst_pipeline.get_by_name('high_vol').set_property('volume', value)

        else:
            print(f' - error, unknown key {key}')

    current_parameters = parameters


def parameter_file_watcher():
    """
    Dynamically reloads the parameter file whenever its modified time changes
    """
    parameter_file = 'two_way_crossover.json'
    mtime = None
    while True:
        _ = os.path.getmtime(parameter_file)
        if _ != mtime:
            mtime = _
            with open(parameter_file) as f:
                reload(json.loads(f.read()))
        time.sleep(1)


gst_pipeline = construct_pipeline()

parameter_file_watcher_thread = threading.Thread(target=parameter_file_watcher)
parameter_file_watcher_thread.run()

GLib.MainLoop().run()
