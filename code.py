import board

CS_PIN = board.GP0
RESET_PIN = board.GP1
CLOCK_PIN = board.GP2
MOSI_PIN = board.GP3
MISO_PIN = board.GP4

import digitalio
import adafruit_rfm69
import busio

# Set up led.
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

# Define radio frequency in MHz. Must match your
# module. Can be a value like 915.0, 433.0, etc.
RADIO_FREQ_MHZ = 915.0

# Define Chip Select and Reset pins for the radio module.
CS = digitalio.DigitalInOut(CS_PIN)
RESET = digitalio.DigitalInOut(RESET_PIN)
spi = busio.SPI(clock=CLOCK_PIN, MOSI=MOSI_PIN, MISO=MISO_PIN)


# Initialise RFM69 radio
rfm69 = adafruit_rfm69.RFM69(spi, CS, RESET, RADIO_FREQ_MHZ)

color_index = 0
# Wait to receive packets.
print("Waiting for packets...")
while True:
    # Look for a new packet - wait up to 5 seconds:
    packet = rfm69.receive(timeout=5.0)
    # If no packet was received during the timeout then None is returned.
    if packet is not None:
        print("Received a packet!")
        # If the received packet is b'button'...
        if packet == b'button':
            led.value = not led.value  # Toggle LED on/off.