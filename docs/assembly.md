# Assembly

The assembly steps contain checks to verify things are working as expected. However they do not include instructions for how to solve these, because there could be a lot of different reasons, e.g. faulty modules, incorrect wiring, bad solder joints, etc.

### The perfboard

#### Power supply

1. Solder a 2-point screw terminal onto the board to connect to the 220V AC -> 12V DC converter's 12V end
2. Solder the 12V -> 5V USB stepsdown converter to the board, and connect to the terminal
3. Plug into to mains and check you see the expected 12V and 5V (on the USB side)
4. Solder the PICO header rails onto the board
5. Create 2 power rails on the long sides of the board
6. Create a connection between the PICO's VBUS (5V out) (pin 40) and the power rail using a jump wire
7. Do the same between the GND rail and a PICO GND pin (i.e. pin 23)
8. Attach a PICO and connect to the mains. Check you see 5V between the power rail and the GND rail.

From this point onwards you can unplug everything from the mains, and disconnect the PICO from the stepdown converter. The power supply is working correctly, and going forward we'll need to test various modules using code, so we will connect the PICO to a development machine (computer) via USB instead.

#### Analog signal readings

To impove reading accuracy we use 2 external ADS1115 modules to read the sensor values. Some 0.1μF ceramic capacitators are also added. When adding these it is easiest to simply colocate them with the jump cable ends, this fits, is space-efficient and saves you having to drag-solder an extra connection.

1. Solder the level shifter onto the board, and establish connections to the PICO and power rail
    1. HV to the 5V power rail
    2. LV to the PICO's 3V3 (OUT) (pin 36)
    3. GND on both sides to the GND rail
    4. LV1 to the PICO's SDA (pin 1)
    5. LV2 tot the PICO's SCL (pin 2)
    6. Add a capacitator on the HV side, between HV and its GND
    7. Add a capacitator on the LV side, between LV and its GND
2. Solder the 2 ADS1115 modules onto the board. For the first one, ensure you leave at least 2 free holes for daisy chaining.
3. Now connect ADS1115-1 and ADS1115-2 to the rails, the level shifter, and each other
    1. Both VDD's to the power rail
    2. Both GND's to the GND rail
    3. ADS1115-1 ADDR to the GND rail
    4. ADS1115-2 ADDR to the 5V rail
    3. ADS1115-1 SCL to HV2 *
    4. ADS1115-1 SDA to HV1 *
    5. ADS1115-1 SCL to ADS1115-2 SCL
    5. ADS1115-1 SDA to ADS1115-2 SDA
4. For each ADS1115, add a capacitator between VDD and ground

**[*] NOTE THAT IN 3 & 4 THE PINS ARE ACTUALLY IN REVERSE ORDER ON THE ADS1115 COMPARED TO THE LEVEL SHIFTER**

To test this setup, you can run the following script on the PICO. If you see a device `0x48` and `0x49` being printed then you can proceed.

```python
from machine import I2C, Pin
import time

i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)

while True:
    print("Scanning I2C bus...")
    devices = i2c.scan()

    if devices:
        for device in devices:
            print("Found device at address: ", hex(device))
    else:
        print("No I2C devices found!")

    time.sleep(2)
```

#### Sensor on/off switches with screw terminals

To extend the lifespan of the sensors from days/week when continiously powered on, to potentially years, we add a MOSFET switch for each sensor, so the sensors are only powered on when they are needed. This limits corrosion to a minimum. The capacitators and resistors are needed in the this setup to deal with these modules not being powered continiously. The wires for each sensor need to be attached to the perfboard in a way that allows disassembly, and for this we use a screw terminal with three pins. So for each sensor we end up with a small cluster of components that fit together as follows, starting from the end-point:
1. Solder the terminal to the perfboard, with the srews facing the GND or 5V rails
2. At the back of the terminal insert a jump wire that can be connected to one of the ADS1115's A0-3 pins. We start with this so the capacitators from step 3-4 can be placed over the top.
3. At the back of the terminal we place a 10μF electrolytic capacitator, ensuring that the positive leg is next to what is to be the VCC/5V pin on the terminal. The negative leg should go with the GND pin of the terminal
4. Beind this we place a 0.1μF ceramic capacitator, with the legs in holes adjacent to the holes used in step 3.
5. Now we drag-solder these sets of three pins togehter:
     1. terminal 5V -> 10μF electrolytic capacitator positive leg -> 0.1μF ceramic capacitator leg
     2. terminal GND -> 10μF electrolytic capacitator negative leg -> 0.1μF ceramic capacitator leg
6. Now connect the GND leg of the 0.1μF ceramic capacitator (5.2) to the GND rail
6. After this we place the MOSFET, with its resistors:
    1. G (Gate): This is the control-pin, so connect to one of the PICO's GP0-20 pins via a 100Ω resistor. It should however also be connected to the GND rail, via a 10kΩ resistor
    2. D (Drain): This is the output pin, so connect it to the 5V power rail
    3. S (Source): This is in input pin, so connect it to the VCC of the terminal, or actually the leg of the 0.1μF ceramic capacitator which is connected to that.
