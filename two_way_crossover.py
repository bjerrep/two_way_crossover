#!/usr/bin/env python3
from enum import Enum
import threading, time, gi, os, json, signal
import amplifierenable

gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst

Gst.init(None)
parameter_file = 'two_way_crossover.json'
current_parameters = {}
verbose = False

gst_pipeline = None

woofer_protect_threshold = None
woofer_protect_attenuation_db_x10 = 0.0

loudness_low_threshold = None
loudness_high_threshold = None
loudness_x20 = 20

NS_IN_SEC = 1000000000


class Configuration(Enum):
    LEFT = 0
    RIGHT = 1
    MONO = 2
    STEREO = 3  # two single stereo output sound cards
    STEREO_40 = 4  # single 5.1/7.1 sound card using front and rear stereo outputs


eq = ['low_eq_29Hz', 'low_eq_59Hz', 'low_eq_119Hz']


def eq_adjust():
    global gst_pipeline
    values = ''

    for band in range(3):
        max = current_parameters[eq[band]]
        min = 0.0
        gain_dB = (max - min) * (loudness_x20 / 20.0) + min
        gain_dB -= woofer_protect_attenuation_db_x10 / 10.0
        if gain_dB < -24.0:
            gain_dB = -24.0

        try:
            for path in range(2):
                gst_pipeline.get_by_name(f'equalizer{path}').set_property(f'band{band}', gain_dB)
                if not path:
                    values += f'{gain_dB:.2f} '
        except:
            pass

    if verbose:
        print((f'equalizer adjusted to {values} (loudness {100.0 * loudness_x20 / 20.0}%, '
               f'protect {woofer_protect_attenuation_db_x10 / 10.0}dB)'))


def bus_message(bus, message):
    global woofer_protect_attenuation_db_x10, loudness_x20
    try:
        if message.has_name('level'):
            s = message.get_structure()
            max_level = -96.0
            for level in s['decay']:
                if level > max_level:
                    max_level = level

            if max_level > -35.0:
                amplifierenable.signal()

            if message.src.get_name().startswith('woofer_protect'):
                exceed_x10 = int((max_level - woofer_protect_threshold) * 10.0)
                if exceed_x10 < 0:
                    exceed_x10 = 0

                if exceed_x10 != woofer_protect_attenuation_db_x10:
                    woofer_protect_attenuation_db_x10 = exceed_x10
                    eq_adjust()

            elif message.src.get_name() == 'loudness':
                loudness_range = loudness_high_threshold - loudness_low_threshold
                if max_level < loudness_low_threshold:
                    loud = 20
                elif max_level > loudness_high_threshold:
                    loud = 0
                else:
                    loud = int(20.0 * (loudness_high_threshold - max_level) / loudness_range)
                if loud != loudness_x20:
                    loudness_x20 = loud
                    eq_adjust()

    except Exception as e:
        print(str(e))


def construct_pipeline(parameters):
    """
    Launch the gstreamer pipeline according to the choosen configuration (from configuration file).
    Bass lift adjustment is made with the low 3 bands of the standard 10 band equalizer which is
    not really the way to do it properly. But it is simple and fairly intuitive to use.
    Also note that there are a total of 3 volume controls per channel to aid when playing
    around, they should probably just be removed.
    """

    print(f'Pipeline starting as \'{parameters["configuration"]}\'')

    # Alsa device selection
    # The primary entry is used for 'left', 'right', 'mono' and 'stereo_40' (anything but 'stereo')
    # Default Alsa device if left empty, use 'device=hw:X' to select a specific device instead
    primary = 'device=hw:0'
    # The secondary entry is the second output alsa device used when running in 'stereo'.
    # Modify to use the correct second soundcard.
    secondary = 'device=hw:X'

    #loudness_element = ''
    #if parameters['loudness'] == 'on':
    loudness_element = f'level name=loudness peak-falloff=3 peak-ttl={3 * NS_IN_SEC} !'

    source = f'alsasrc {primary}'
    if parameters['test_source'] == 'on':
        source = f'audiotestsrc name=testsource freq=1000.0 ! volume name=testvolume volume=0.1'

    # Input Alsa device is always the primary from above.
    input = (f'{source} ! audioconvert ! audio/x-raw,format=F32LE,channels=2 ! '
             f'{loudness_element} queue ! ')

    configuration = Configuration[parameters['configuration'].upper()]

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

        woofer_protect_element = ''
        if parameters['woofer_protect'] == 'on':
            woofer_protect_element = f'level name=woofer_protect{path} ! '

        if not path or (configuration == Configuration.STEREO):
            if path and (configuration == Configuration.STEREO):
                interleave_element = 1

            output = (f'interleave name=i{interleave_element} ! '
                      f'audioconvert ! audioresample ! queue ! '
                      f'{woofer_protect_element} '
                      f'alsasink name=alsasink{path} {alsa_devices[path]} '
                      f'sync=true buffer-time={parameters["buffer-time"]} ')

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

    if parameters['woofer_protect'] == 'on' or parameters['loudness'] == 'on':
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect('message::element', bus_message)

    print((f' - woofer protection: {parameters["woofer_protect"]}, loudness: {parameters["loudness"]}, '
           f'test source: {parameters["test_source"]}'))

    return pipeline


def reload(parameters):
    global gst_pipeline, woofer_protect_threshold, loudness_low_threshold, loudness_high_threshold, verbose
    """
    There is no sanity checking so you get what you ask for. Lookup the documentation
    for the gstreamer elements if in doubt about what sane values could look like.
    Keep master volume above 0.001 or the pipeline will stop (!?).
    """
    global current_parameters, gst_pipeline

    print('reloading parameters')

    woofer_protect_threshold = parameters['woofer_protect_threshold']
    loudness_low_threshold = parameters['loudness_low_threshold']
    loudness_high_threshold = parameters['loudness_high_threshold']
    verbose = parameters['test_verbose']

    restart_pipeline = False

    if (not current_parameters or
        parameters['woofer_protect'] != current_parameters['woofer_protect'] or
        parameters['loudness'] != current_parameters['loudness'] or
        parameters['test_source'] != current_parameters['test_source'] or
        parameters['buffer-time'] != current_parameters['buffer-time'] or
        parameters['configuration'] != current_parameters['configuration']):
        restart_pipeline = True

    if restart_pipeline or not gst_pipeline:
        if gst_pipeline:
            gst_pipeline.set_state(Gst.State.NULL)
        gst_pipeline = construct_pipeline(parameters)

    modified = dict(parameters.items() - current_parameters.items())

    for key, value in sorted(modified.items()):

        for path in [Configuration.LEFT.value, Configuration.RIGHT.value]:
            try:
                # Bass crossover, equalizer and volume.
                if key == 'low_frequency':
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
                    # will have forced a pipeline restart above with the new value. Can't be changed while running ?
                    continue
                elif key == 'test_volume':
                    gst_pipeline.get_by_name(f'testvolume').set_property('volume', value)
                elif key == 'test_frequency':
                    gst_pipeline.get_by_name(f'testsource').set_property('freq', value)
                else:
                    continue

                print(f' - setting {key} (channel {path}) to {value}')

            except AttributeError:
                pass

    current_parameters = parameters

    if gst_pipeline.get_state(Gst.CLOCK_TIME_NONE) != Gst.State.PLAYING:
        gst_pipeline.set_state(Gst.State.PLAYING)
        error_message = gst_pipeline.get_bus().pop_filtered(Gst.MessageType.ERROR)
        if error_message:
            err, msg = error_message.parse_error()
            print(f'\nFatal error: \n{err}\n\n{msg}\n')
            exit(1)


def parameter_file_watcher():
    """
    Dynamically reloads the parameter file whenever its modified time changes
    """
    mtime = None
    while True:
        _ = os.path.getmtime(parameter_file)
        if _ != mtime:
            mtime = _
            with open(parameter_file) as f:
                reload(json.loads(f.read()))
        time.sleep(1)


def ctrl_c_handler(_, __):
    print(' ctrl-c handler')
    os._exit(1)


signal.signal(signal.SIGINT, ctrl_c_handler)

parameter_file_watcher_thread = threading.Thread(target=parameter_file_watcher)
parameter_file_watcher_thread.start()

GLib.MainLoop().run()
