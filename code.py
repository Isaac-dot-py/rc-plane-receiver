# BEFORE YOU GET CONFUSED, THE BUTTONS ARE NAMED AFTER A ONE BASED INDEXING SYSTEM, BUT THE RECEIVED LIST OF BUTTON PRESSES IS ZERO BASED

import digitalio
import adafruit_rfm69
import busio
import board
from adafruit_motor import servo
import pwmio
from time import sleep

CS_PIN = board.GP0
RESET_PIN = board.GP1
CLOCK_PIN = board.GP2
MOSI_PIN = board.GP3
MISO_PIN = board.GP4
RADIO_FREQ_MHZ = 915.0
MIN_THROTTLE = 0
MAX_THROTTLE = 180
ELEVATOR_CENTER = 96
ELEVAROR_GAIN = -20
RUDDER_CENTER = 102
RUDDER_GAIN = -20
LEFT_FLAPERON_CENTER = 90
RIGHT_FLAPERON_CENTER = 90
AILERON_GAIN = 1


led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

elevator = servo.Servo(pwmio.PWMOut(board.GP21, duty_cycle=2**15, frequency=50))
elevator.angle = ELEVATOR_CENTER
rudder = servo.Servo(pwmio.PWMOut(board.GP20, duty_cycle=2**15, frequency=50))
rudder.angle = RUDDER_CENTER
left_flaperon = servo.Servo(pwmio.PWMOut(board.GP19, duty_cycle=2**15, frequency=50))
right_flaperon = servo.Servo(pwmio.PWMOut(board.GP18, duty_cycle=2**15, frequency=50))
flap_angle = 0
throttle_servo = servo.Servo(pwmio.PWMOut(board.GP22, duty_cycle=2**15, frequency=50))
throttle_servo.angle = 0

armed = False
taxiing = False # reduces throttle to 10% of what it would be

def calculate_flaperons(
    difference_aileron, loose_average_flap, minimum_output=-1, maximum_output=1
):
    # all numbers -1 to 1
    if abs(difference_aileron) > maximum_output - minimum_output:
        return (
            (maximum_output, minimum_output)
            if difference_aileron > 0
            else (minimum_output, maximum_output)
        )
    average_modified_to_respect_bounds = max(
        minimum_output + abs(difference_aileron) / 2,
        min(maximum_output - abs(difference_aileron) / 2, loose_average_flap),
    )
    return (
        average_modified_to_respect_bounds + difference_aileron / 2,
        average_modified_to_respect_bounds - difference_aileron / 2,
    )




HAT_TO_DEGREES = (0, 45, 90, 135, 180, 225, 270, 315, -1)  # 8=centered -> -1
def parse_report(data):
    if len(data) < 7:
        print("Invalid data length: " + str(len(data)))
        return None

    x = data[0] | ((data[1] & 0x03) << 8)  # 0..1023
    y = (data[1] >> 2) | ((data[2] & 0x0F) << 6)  # 0..1023
    hat_nibble = data[2] >> 4  # 0..8 (8 = centered)
    twist = data[3]  # 0..255
    buttons_a = data[4]
    slider = data[5]  # 0..255
    buttons_b = data[6]

    axes = [x, y, twist, slider]  # index 0=X, 1=Y, 2=twist(Z), 3=slider/throttle

    buttons_mask = buttons_a | (buttons_b << 8)
    buttons = [bool(buttons_mask & (1 << i)) for i in range(12)]  # 12 buttons

    pov = HAT_TO_DEGREES[hat_nibble] if hat_nibble < len(HAT_TO_DEGREES) else -1

    return axes, buttons, pov


if False:
    # center servos
    elevator.angle = 90
    rudder.angle = 90
    left_flaperon.angle = 90
    right_flaperon.angle = 90
    sleep(1000000)
if False:
    # wiggle servos to test
    while True:
        for angle in range(50, 131, 10):
            elevator.angle = angle
            rudder.angle = angle
            left_flaperon.angle = angle
            right_flaperon.angle = angle
            sleep(0.1)
        for angle in range(130, 49, -10):
            elevator.angle = angle
            rudder.angle = angle
            left_flaperon.angle = angle
            right_flaperon.angle = angle
            sleep(0.1)

radio_cs = digitalio.DigitalInOut(CS_PIN)
radio_reset = digitalio.DigitalInOut(RESET_PIN)
radio_spi = busio.SPI(clock=CLOCK_PIN, MOSI=MOSI_PIN, MISO=MISO_PIN)

rfm69 = adafruit_rfm69.RFM69(radio_spi, radio_cs, radio_reset, RADIO_FREQ_MHZ)

rssi_history = [0] * 30

# Wait to receive packets.
print("Waiting for packets...")
while True:
    # Look for a new packet - wait up to 5 seconds:
    received_bytes = rfm69.receive(timeout=5.0)
    # If no packet was received during the timeout then None is returned.
    if received_bytes is not None:
        parsed = parse_report(received_bytes)
        if parsed is None:
            print("Invalid state data: " + received_bytes.decode())
            continue
        axes, buttons, pov = parsed
            # buttons 7 and 8 are arming buttons, arm when both are pressed and throttle is at minimum
        if buttons[6] and buttons[7] and axes[3] > 0.95 * 255:
            armed = True
        # Disarm when button 11 is pressed
        if buttons[10]:
            armed = False

        if buttons[9]:
            taxiing = False
        if buttons[11]:
            taxiing = True

        if buttons[2] and flap_angle < 40:
            flap_angle += 1
        if buttons[4] and flap_angle > 0:
            flap_angle -= 1

        # Map input (0 to 1023) to angle (0 to 180)
        elevator.angle = -(axes[1] / 1023.0 * 2 - 1) * ELEVAROR_GAIN + ELEVATOR_CENTER
        # print(f"elevator angle {elevator.angle}")
        rudder.angle = (axes[2] / 255.0 * 2 - 1) * RUDDER_GAIN + RUDDER_CENTER
        # print(f"axes[2]: {axes[2]}, minus 1 to 1 number: {(axes[2] / 255.0 * 2 - 1)}, rudder angle {rudder.angle}")

        aileron_calculation_result = calculate_flaperons(
            (axes[0] / 1023.0 * 2 - 1), flap_angle / 90
        )
        # print((axes[0] / 1023.0 * 2 - 1))
        left_flaperon.angle = -aileron_calculation_result[0]*90+90
        right_flaperon.angle = aileron_calculation_result[1]*90+90

        throttle_angle = (
            int(((255.0 - axes[3]) / 255.0) * (0.1 if taxiing else 1.0) * (MAX_THROTTLE - MIN_THROTTLE) + MIN_THROTTLE)
            if armed
            else 0
        )
        print(f"throttle_angle: {throttle_angle}, armed: {armed}, taxiing: {taxiing}")
        throttle_servo.angle = throttle_angle
        rssi_history.append(rfm69.last_rssi)
        if len(rssi_history) > 30:
            rssi_history.pop(0)
        avg_rssi = sum(rssi_history) / len(rssi_history)
        # print(
        #     f"rfm69.last_rssi: {rfm69.last_rssi}, Avg RSSI: {avg_rssi:.1f}",
        #     end="\r",
        # )
        # print(" ".join(f"{b:02x}" for b in received_bytes), "axes:", axes, "buttons:", buttons, "pov:", pov)
    else:
        print("Received nothing!")