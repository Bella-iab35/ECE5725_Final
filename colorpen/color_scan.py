#!/usr/bin/python3


import time
import board
import os
import json
import bluetooth
from adafruit_apds9999 import APDS9999
from adafruit_apds9960.apds9960 import APDS9960
import RPi.GPIO as GPIO
import digitalio
from PIL import Image, ImageDraw, ImageFont, ImageSequence
import adafruit_ssd1306


# Bluetooth setup
PI4_MAC = "DC:A6:32:B4:14:E2"
BT_PORT = 1


def send_color(r, g, b):
   """Send a single color reading to the Pi 4 over Bluetooth RFCOMM."""
   try:
       sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
       sock.connect((PI4_MAC, BT_PORT))
       payload = json.dumps({"r": r, "g": g, "b": b})
       sock.send(payload.encode("utf-8"))
       sock.close()
       print(f"Sent over Bluetooth: {payload}")
       return True
   except Exception as e:
       print(f"Bluetooth send failed: {e}")
       return False


# Set up color sensor
sensor = APDS9999(board.I2C())
sensor.light_sensor_enabled = True
sensor.rgb_mode = True
sensor.proximity_sensor_enabled = True
#sensor.enable_color = True


# Set up button
button = 4
GPIO.setmode(GPIO.BCM)
GPIO.setup(button, GPIO.IN, pull_up_down=GPIO.PUD_UP)


# Set up OLED
oled_reset = digitalio.DigitalInOut(board.D4)
WIDTH = 128
HEIGHT = 64
BORDER = 5
i2c = board.I2C()
oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=0x3C, reset=oled_reset)


oled.fill(0)
oled.show()


# Initializing Images
start_im = Image.new("1", (oled.width, oled.height))
scanning = ImageSequence.Iterator(Image.open("Eyedropper64.gif"))
end_im = Image.new("1", (oled.width, oled.height))


font = ImageFont.load_default()


states = {
   0: "start",
   1: "scan",
   2: "end"
}


curr_state = states[0]
i = 0


# Track the latest reading during a scan
latest_r, latest_g, latest_b = 0, 0, 0


while True:
   if curr_state == states[0]:
       draw = ImageDraw.Draw(start_im)
       text = "Tap button to\n scan color!"
       bbox = font.getbbox(text)
       (font_width, font_height) = bbox[2] - bbox[0], bbox[3] - bbox[1]
       draw.text(
           (oled.width // 2, oled.height // 2),
           text, font=font, fill=255, anchor="ms"
       )


       oled.image(start_im)
       oled.show()


       if GPIO.input(button) == GPIO.LOW:
           curr_state = states[1]
           start_time = time.time()
       else:
           pass


   elif curr_state == states[1]:
       image = scanning[i].convert("1")
       print(f"Current frame: {i}")
       oled.image(image)
       oled.show()
       i = i + 1
       if i == 95:
           i = 0


       r, g, b, ir = sensor.rgb_ir
       lux = sensor.calculate_lux(g)
       print(
           f"r: {r}, g: {g}, b: {b}, lux{lux}"
           #f"lux: {sensor.calculate_lux(g)} proximity: {sensor.proximity}"
       )


       latest_r, latest_g, latest_b = r, g, b


       if time.time()-start_time >= 7:


           # White-balance weights calibrated against printer paper
           # Raw white reference: r=216, g=274, b=77
           R_WEIGHT = 1.27
           G_WEIGHT = 1.00
           B_WEIGHT = 2.56


           r_corrected = latest_r * R_WEIGHT
           g_corrected = latest_g * G_WEIGHT
           b_corrected = latest_b * B_WEIGHT


           max_val = max(r_corrected, g_corrected, b_corrected, 1)
           r_norm = r_corrected / max_val
           g_norm = g_corrected / max_val
           b_norm = b_corrected / max_val


           # Saturation boost — push lower channels toward 0 to make colors pop
           SATURATION_POWER = 2.5
           r_sat = r_norm ** SATURATION_POWER
           g_sat = g_norm ** SATURATION_POWER
           b_sat = b_norm ** SATURATION_POWER


           max_sat = max(r_sat, g_sat, b_sat, 0.001)
           r8 = round((r_sat / max_sat) * 255)
           g8 = round((g_sat / max_sat) * 255)
           b8 = round((b_sat / max_sat) * 255)


           print(f"Raw: r={latest_r} g={latest_g} b={latest_b}")
           print(f"Corrected: r={r_corrected:.0f} g={g_corrected:.0f} b={b_corrected:.0f}")
           print(f"Final scaled color: r={r8} g={g8} b={b8}")
           send_color(r8, g8, b8)


           curr_state = states[2]
           start_time = time.time()
           i = 0
   else:
       draw = ImageDraw.Draw(end_im)
       text = "Color scanned!"
       bbox = font.getbbox(text)
       (font_width, font_height) = bbox[2] - bbox[0], bbox[3] - bbox[1]
       draw.text(
           (oled.width // 2, oled.height // 2),
           text, font=font, fill=255, anchor="ms"
       )


       oled.image(end_im)
       oled.show()


       if time.time() - start_time >= 5:
           curr_state = states[0]
