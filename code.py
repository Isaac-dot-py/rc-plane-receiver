import digitalio
import adafruit_rfm69
import busio
from gamepad_state import GamepadState
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
ELEVATOR_CENTER = 90
ELEVAROR_GAIN = 20
RUDDER_CENTER = 90
RUDDER_GAIN = 20
LEFT_FLAPERON_CENTER = 90
RIGHT_FLAPERON_CENTER = 90
AILERON_GAIN = 20 / 90


led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT

elevator = servo.Servo(pwmio.PWMOut(board.GP21, duty_cycle=2**15, frequency=50))
rudder = servo.Servo(pwmio.PWMOut(board.GP20, duty_cycle=2**15, frequency=50))
left_flaperon = servo.Servo(pwmio.PWMOut(board.GP19, duty_cycle=2**15, frequency=50))
right_flaperon = servo.Servo(pwmio.PWMOut(board.GP18, duty_cycle=2**15, frequency=50))
flap_angle = 0
throttle_servo = servo.Servo(pwmio.PWMOut(board.GP22, duty_cycle=2**15, frequency=50))
throttle_servo.angle = 0

armed = False


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


if True:
    # center servos
    elevator.angle = 90
    rudder.angle = 90
    left_flaperon.angle = 90
    right_flaperon.angle = 90
    sleep(10000)
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
    gamepadstate_in_bytes = rfm69.receive(timeout=5.0)
    # If no packet was received during the timeout then None is returned.
    if gamepadstate_in_bytes is not None:
        # Create a GamepadState from the bytes
        state = GamepadState.from_bytes(gamepadstate_in_bytes)
        if state:
            # C2 is arming button, arm when C2 is pressed and throttle is at minimum
            if state.C2 and not armed and state.LY < -0.95:
                armed = True
            # Disarm when C1 is pressed
            if state.C1 and armed:
                armed = False

            # Map input (-1 to 1) to angle (0 to 180)
            elevator.angle = state.RY * ELEVAROR_GAIN + ELEVATOR_CENTER
            rudder.angle = state.RX * RUDDER_GAIN + RUDDER_CENTER

            aileron_calculation_result = calculate_flaperons(
                state.RX * AILERON_GAIN, flap_angle / 90, 180
            )
            left_flaperon.angle = aileron_calculation_result[0]
            right_flaperon.angle = aileron_calculation_result[1]

            throttle_angle = (
                int(((state.LY + 1) / 2) * (MAX_THROTTLE - MIN_THROTTLE) + MIN_THROTTLE)
                if armed
                else 0
            )
            throttle_servo.angle = throttle_angle
            rssi_history.append(rfm69.last_rssi)
            if len(rssi_history) > 30:
                rssi_history.pop(0)
            avg_rssi = sum(rssi_history) / len(rssi_history)
            print(
                f"rfm69.last_rssi: {rfm69.last_rssi}, Avg RSSI: {avg_rssi:.1f}",
                end="\r",
            )
            # print(
            #     f"Right Y: {round(state.RY, 2):<5}, Angle: {angle1:<3}, Right X: {round(state.RX, 2):<5}, Angle: {angle2:<3}, Left Y: {round(state.LY, 2):<5}, Throttle Angle: {throttle_angle:<3}, Left X: {round(state.LX, 2):<5}, Angle: {angle4:<3}",
            #     end="\r",
            # )
        else:
            print("Invalid state data: " + gamepadstate_in_bytes.decode())
