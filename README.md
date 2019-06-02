
# Two Way Crossover

A minimalist project about using a computer and a sound card to quickly produce a two way crossover filter for an analog audio signal chain. It is intended to be used for anything from quick tests and experiments to be installed on e.g. a Raspberry Pi Zero and get permanently embedded in a diy speaker setup.

<p align="center"><img width=400 src="images/response.png"></p>

This projects primary goal is simplicity of use. There are a lot of super nice projects that does the same but they all seem to delivery more features (and design quality) at the expense of added complexity in getting things up and running. And probably a fair guess is that a lot of potential users for a project like this have little or limited experience with linux. Unfortunately even this project still requires at least a little experience with audio on a linux machine.

This is not a HiFi project. It happily decreases the signal to noise ratio by letting the signal pass a couple of 16 bit converters in a sound card most likely chosen from its price tag, just to be filtered by filters with allowed ripple in the pass bands. In other words it probably looks like a lot of consumer audio does these days and chances are that it will do just fine for a lot of diy audio projects.

Implementing the design requirements in software rather than hardware means that just about everything is suddenly infinitely tweakable. Currently the default behavior is tailored towards small and size constrained closed enclosures and it incorporates a bass lift intended to work below the natural low corner frequency to get 'an extra octave' in the low end. (*)

(*) This of course come at a cost. A relatively lot of power might be delivered in the woofer which is basically asked to play in a range where it by nature can't really produce sound. So at least one effect of this is that the max power rating and max cone excursion gets exhausted at a lower apparent sound level than without the boost. So it is a solution for quality rather than quantity. Typically a compensation filter like this for a closed box would be a 6 dB/oct filter but right now its just a couple of bands from a 10 band equalizer.

## Get started

1. Fire up a linux computer with a sound card
2. Install alsa, gstreamer and python 3 if they are not already available
3. Clone the software
4. Run the python script

You now have a single channel digital-analog crossover filter thanks to gstreamer. Default crossover at 2kHz (8'th order 0.25dB ripple Chebyshew) and a 6 dB boost at 59 Hz. Bass in left channel and treble in right channel. A stereo filter will be easy to add in the code and will require an extra sound card since 4 outputs will be needed in total.

## Get started notes

1. Only Arch Linux have been tested but there is no reason to believe that other distroes will misbehave. If using a USB sound card then get one with a real line-in input, assuming that the setup should be based on line signals in the first place. The average headset dongles have mic-in and can be used for testing but most doesn't really belong in a setup like this.
2. If using a Pi Zero then a network connection is -very- nice while setting up the filter.
Some example fire and forget install commands are pending..
3. Make a git clone
4. Execute

    $python two_way_crossover.py
    
Woofer signal will be in left output, tweeter in right output. The script uses the default alsa devices ('hw:0'), use 'aplay -l' to verify if e.g. a USB soundcard is device 1 or larger and modify the script accordingly.


# Get tweaking

The central adjustable parameters are found in the configuration file two_way_crossover.json. It is automatically reloaded and applied when modified, there is no reason to restart the python script. If working on a remote computer then start a second ssh for playing with the parameter file. Feel free to use the issue tracker for rants and questions and pull requests for fixes and any nice stuff.


# Links

[Pulseaudio Crossover Rack](https://t-5.eu/hp/Software/Pulseaudio%20Crossover%20Rack)

