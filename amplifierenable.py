import threading, time

try:
    import RPi.GPIO as GPIO
except Exception as e:
    print('gpio disabled')
    GPIO = False


amp_enable_pin = 15
downcounter = 0
idle_seconds = 3


def signal():
    global downcounter
    downcounter = idle_seconds * 10


def amplifier_enable():
    global downcounter
    while True:
        time.sleep(0.1)
        if downcounter:
            if downcounter == idle_seconds * 10:
                GPIO.output(amp_enable_pin, 0)

            downcounter -= 1
            if not downcounter:
                print('amplifier disable')
                GPIO.output(amp_enable_pin, 1)


if GPIO:
    print('amplifier control starting')
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(amp_enable_pin, GPIO.OUT)
    GPIO.output(amp_enable_pin, 1)
    thread = threading.Thread(target=amplifier_enable)
    thread.start()

