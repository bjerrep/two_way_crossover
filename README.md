
# Two Way Crossover

A minimalist project about using a computer and a sound card to quickly produce a two way crossover filter for an analog audio signal chain. It is intended to be used for anything from quick tests and experiments to be installed on e.g. a Raspberry Pi Zero and get permanently embedded in a diy speaker setup.

<p align="center"><img width=400 src="images/response.png"></p>

This projects primary goal is simplicity of use. There are a lot of super nice projects that does the same but they all seem to delivery more features (and design quality) at the expense of added complexity in getting things up and running. And probably a fair guess is that a lot of potential users for a project like this have little or limited experience with linux. Unfortunately even this project still requires at least a little experience with audio on a linux machine.

This is not a HiFi project. It happily decreases the signal to noise ratio by letting the signal pass a couple of 16 bit converters in a sound card most likely chosen from its price tag, just to be filtered by filters with allowed ripple in the pass bands. In other words it probably looks like a lot of consumer audio does these days and chances are that it will do just fine for a lot of diy audio projects.

Implementing the design requirements in software rather than hardware means that just about everything is suddenly infinitely tweakable. Currently the default behavior is tailored towards small and size constrained closed enclosures and it incorporates a bass lift intended to work below the natural low corner frequency to get 'an extra octave' in the low end. (*)

(*) This of course come at a cost. A relatively lot of power might be delivered in the woofer which is basically asked to play in a range where it by nature can't really produce sound. So at least one effect of this is that the max power rating and max cone excursion gets exhausted at a lower apparent sound level than without the boost. So it is a solution for quality rather than quantity. Typically a compensation filter like this for a closed box would be a 6 dB/oct filter but right now its just a couple of bands from a 10 band equalizer.

Please be aware that this project currently is to be considered slightly unstable. It is known to seamleesly introduce  changes and break things at the same time. The status 'works' might be read as 'works or once did'.

| computer 	| status                                  	|
|----------	|-----------------------------------------	|
| x86      	| works                                   	|
| RPI 3B+  	| works                                   	|
| RPI 1B+  	| only noise with Arch                    	|
| Zero     	| not tested (same but faster cpu as 1B+) 	|


## Get started

1. Fire up a linux computer with a sound card
2. Install alsa, gstreamer and python 3 if they are not already available
3. Clone the software
4. Run the python script

You now have a single channel digital-analog crossover filter thanks to gstreamer. Default is mono operation and a crossover at 2kHz (8'th order 0.25dB ripple Chebyshew) and a 6 dB boost at 59 Hz. Bass in left channel and treble in right channel.

## Get started notes

1. Only Arch Linux have been tested but there is no reason to believe that other distroes will misbehave. If using a USB sound card then get one with a real line-in input, assuming that the setup should be based on line signals in the first place. The average headset dongles have mic-in and can be used for testing but most doesn't really belong in a setup like this.
2. Fire and forget install lines

    Arch : git gstreamer gst-plugins-good gst-plugins-base alsa alsa-tools alsa-utils gst-python

3. Make a git clone
4. Execute

    $python two_way_crossover.py

Woofer signal will be in left output, tweeter in right output. The script uses the default alsa devices ('hw:0'), use 'aplay -l' to verify if e.g. a USB soundcard is device 1 or larger and modify the script accordingly.

There is a template for a systemd service file in ./systemd that might be of help in case the script should start at boot time.

# Get tweaking

The central adjustable parameters are found in the configuration file two_way_crossover.json. 

The overall configuration can be set to 'left', 'right', 'mono' or 'stereo'. The configuration file is automatically reloaded and applied when modified (except for the configuration value), there is no reason to restart the python script as long as it is only the numeric values that are changed. 

Here is an image of what a stereo crossover filter with a RPI 3B+ could look like :

<p align="center"><img src="images/stereo.jpg"></p>

Feel free to use the issue tracker for rants and questions and pull requests for fixes and any nice stuff.


# Links

[Pulseaudio Crossover Rack](https://t-5.eu/hp/Software/Pulseaudio%20Crossover%20Rack)

