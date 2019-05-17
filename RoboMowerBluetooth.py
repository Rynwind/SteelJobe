#!/usr/bin/python2
 
# Load library functions we want
from __future__ import print_function, division
from pysabertooth import Sabertooth
import os
import pygame
import serial
import serial.tools.list_ports
import sys
import time

 # Re-direct our output to standard error, we need to ignore standard out to hide some nasty print statements from pygame
sys.stdout = sys.stderr

#Connect to Sabertooth via USB serial.
for my_port in serial.tools.list_ports.grep("sabertooth"):
    port = my_port.device

# Settings for the joystick
axisUpDown = 1                          # Joystick axis to read for up / down position
axisUpDownInverted = False              # Set this to True if up and down appear to be swapped
axisLeftRight = 3                       # Joystick axis to read for left / right position
axisLeftRightInverted = False           # Set this to True if left and right appear to be swapped
buttonSlow = 4                          # Joystick button number for driving slowly whilst held (L2)
buttonPSExit = 10                       # Joystick button number for exiting and restarting script.
buttonFreeWheel = 9                     # Joystick button number for turning freewheel on for both motors.
slowFactor = 0.5                        # Speed to slow to when the drive slowly button is held, e.g. 0.5 would be half speed
buttonFastTurn = 5                      # Joystick button number for turning fast (R2)
interval = 0.10                         # Time between updates in seconds, smaller responds faster but uses more processor time
noMovementFlag = 0                      # Flag to track if no movement is desired by press of freeWheel button, toggled
lastEvent = time.time()                 # Time of last event, just in case no input - stop after 2 seconds of no input
noEventTimeout = 1                      # seconds until timeout with no event, set back to 0 speed.
# Power settings
voltageIn = 24.0                        # Total battery voltage to the Sabertooth
voltageOut = 24.0 * 0.95                # Maximum motor voltage, we limit it to 95% to allow the RPi to get uninterrupted power
 
# Setup the power limits
if voltageOut > voltageIn:
    maxPower = 100
else:
    maxPower = voltageOut / float(voltageIn)
 
# Setup pygame and wait for the joystick to become available
saber = Sabertooth(port, baudrate=9600)
print('temperature [C]: {}'.format(saber.textGet(b'm2:gett')))
print('battery [mV]: {}'.format(saber.textGet(b'm2:getb')))
saber.text(b'm1:startup')
saber.text(b'm2:startup')

print('Pygame os display settings')
os.environ["SDL_VIDEODRIVER"] = "dummy" # Removes the need to have a GUI window
os.putenv('SDL_VIDEODRIVER', 'fbcon')

print('Pygame init')
pygame.init()
print('Pygame display init')
pygame.display.init()
print('Pygame display set')
pygame.display.set_mode((1,1))

print ('Waiting for joystick... press CTRL+C to abort')

while True:
    try:
        try:
            pygame.joystick.init()
            # Attempt to setup the joystick
            if pygame.joystick.get_count() < 1:
                # No joystick attached
                pygame.joystick.quit()
                time.sleep(0.1)
            else:
                # We have a joystick, attempt to initialise it!
                joystick = pygame.joystick.Joystick(0)
                break
        except pygame.error:
            # Failed to connect to the joystick
            pygame.joystick.quit()
            time.sleep(0.1)
    except KeyboardInterrupt:
        # CTRL+C exit, give up
        print ("\nUser aborted")
        saber.stop()
        sys.exit()
print ('Joystick found')
joystick.init()

 
try:
    print ('Press CTRL+C to quit')
    driveLeft = 0.0
    driveRight = 0.0
    running = True
    hadEvent = False
    upDown = 0.0
    leftRight = 0.0
    oldspeed1 = 0
    oldspeed2 = 0
    noRecentEventFlag = 1
    stopButtonPSExitFlag = 0
    # Loop indefinitely
    while running:
        # Check how long since lastEvent, stop if greater than or equal to noEventTimeout in seconds
        now = time.time()
        secondsDiff = (now - lastEvent) % 60
        if secondsDiff >= noEventTimeout and noRecentEventFlag == 0:
            noRecentEventFlag = 1
            saber.text(b'm1:0')
            saber.text(b'm2:0')
            print ('Stopped due to no events in last{}'.format(noEventTimeout))
        # Get the latest events from the system
        hadEvent = False
        events = pygame.event.get()
        # Handle each event individually
        for event in events:
            if event.type == pygame.QUIT:
                # User exit
                running = False
            elif event.type == pygame.JOYBUTTONDOWN:
                # A button on the joystick just got pushed down
                hadEvent = True
            elif event.type == pygame.JOYAXISMOTION:
                # A joystick has been moved
                hadEvent = True
            if hadEvent:
                #track time and set noRecentEventFlag to 0 to prevent stop
                noRecentEventFlag = 0
                lastEvent = time.time()

                # break out if PS button is pressed
                if joystick.get_button(buttonPSExit):
                    stopButtonPSExitFlag = 1
                    saber.drive(1, 0)
                    saber.drive(2, 0)

                if joystick.get_button(buttonFreeWheel):
                    if noMovementFlag == 0:
                        noMovementFlag = 1
                        saber.text(b'm1:0')
                        saber.text(b'm2:0')
                        saber.text(b'q1:1')
                        saber.text(b'q2:1')
                    else:
                        noMovementFlag = 0
                        saber.text(b'm1:0')
                        saber.text(b'm2:0')
                        saber.text(b'q1:0')
                        saber.text(b'q2:0')

                # Read axis positions (-1 to +1)
                if axisUpDownInverted:
                    upDown = -joystick.get_axis(axisUpDown)
                else:
                    upDown = joystick.get_axis(axisUpDown)
                if axisLeftRightInverted:
                    leftRight = -joystick.get_axis(axisLeftRight)
                else:
                    leftRight = joystick.get_axis(axisLeftRight)
                # Apply steering speeds
                if not joystick.get_button(buttonFastTurn):
                    leftRight *= 0.5
                # Determine the drive power levels
                driveLeft = -upDown
                driveRight = -upDown
                if leftRight < -0.05:
                    # Turning left
                    driveRight *= 1.0 + (2.0 * leftRight)
                elif leftRight > 0.05:
                    # Turning right
                    driveLeft *= 1.0 - (2.0 * leftRight)
                # Check for button presses
                if joystick.get_button(buttonSlow):
                    driveLeft *= slowFactor
                    driveRight *= slowFactor
                # Set the motors to the new speeds if the speed has changed
                speed1 = (driveLeft  * maxPower)
                speed2 = (driveRight * maxPower)
                saberspeed1 = int((speed1 * 2047))
                saberspeed2 = int((speed2 * 2047))
                #print(upDown, leftRight, speed1, speed2)
                #print (speed1, saberspeed1, speed2, saberspeed2)
                if speed1 != oldspeed1:
                    oldspeed1 = speed1
                    if noMovementFlag == 0:
                        saber.text(b'm1:{}'.format(saberspeed1))
                if speed2 != oldspeed2:
                    oldspeed2 = speed2
                    if noMovementFlag == 0:
                        saber.text(b'm2:{}'.format(saberspeed2))

        # Wait for the interval period
        time.sleep(interval)
except KeyboardInterrupt:
    # CTRL+C exit
    print ('\nUser shutdown')
    saber.drive(1, 0)
    saber.drive(2, 0)
    saber.stop()
print