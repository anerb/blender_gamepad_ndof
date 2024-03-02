# Aner Ben-Artzi 2024
# License: GPL

bl_info = {
    "name": "Gamepad NDOF View Controller",
    "description": "Control the blender viewport using a gamepad.",
    "author": "Aner Ben-Artzi",
    "version": (0, 1), 
    "blender": (4, 0, 0),
    "location": "Always active in the 3D View",
    "warning": "Only tested for one controller and one 3D View.",
    "doc_url": "https://anerb.github.io/blender_gamepad_ndof",
    "support": "TESTING",
    "category" : "3D View",
}


def installPysdl():
    import subprocess
    import sys

    py_exec = sys.executable
    # ensure pip is installed & update
    subprocess.call([str(py_exec), "-m", "ensurepip", "--user"])
    subprocess.call([str(py_exec), "-m", "pip", "install", "--upgrade", "pip"])
    # install dependencies using pip
    # dependencies such as 'numpy' could be added to the end of this command's list
    subprocess.call([str(py_exec),"-m", "pip", "install", "--user", "pysdl2"])

import bpy
import mathutils
import math
try:
  import sdl2
  import sdl2.ext
except (ModuleNotFoundError):
  installPysdl()
  import sdl2
  import sdl2.ext
  


def getActiveView3d():
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            return area.spaces[0].region_3d

def home(view3d):
    view3d.view_location = mathutils.Vector((0, 0, 0))
    view3d.view_distance = 10
    view3d.view_rotation = mathutils.Quaternion((0.8151376843452454, 0.4413430094718933, 0.17513969540596008, 0.33180227875709534))


# positive is clockwise
def roll(view3d, amount):
    if amount == 0:
        return
    pureZ = mathutils.Vector((0, 0, 1))
    view_matrix3 = view3d.view_matrix.to_3x3()
    inverted_view_matrix = view_matrix3.inverted_safe()
    view_direction = inverted_view_matrix @ pureZ
    view_direction.normalize()
    view_vector = view_direction * amount
    roll_quaternion = mathutils.Euler(view_vector).to_quaternion()
    view3d.view_rotation.rotate(roll_quaternion)

def orbit(view3d, mouseX, mouseY, amount):
    if amount == 0 or (mouseX == 0 and mouseY == 0):
        return
    amount *= (1/10)
    pureZ = mathutils.Vector((0, 0, 1))
    mouse_vector = mathutils.Vector((mouseX, mouseY, 1))
    view_matrix3 = view3d.view_matrix.to_3x3()
    inverted_view_matrix = view_matrix3.inverted_safe()
    screen_origin = inverted_view_matrix @ pureZ
    screen_mouse = inverted_view_matrix @ mouse_vector
    orbit_vector = screen_mouse - screen_origin
    orbit_vector_scaled = orbit_vector * amount
    orbit_quaternion = mathutils.Euler(orbit_vector_scaled).to_quaternion()
    view3d.view_rotation.rotate(orbit_quaternion)
    view3d.view_perspective = 'PERSP'


# For now, just  move forward by amount
def dolly(view3d, amount):
    if amount == 0:
        return
    pureZ = mathutils.Vector((0, 0, 1))
    view_matrix3 = view3d.view_matrix.to_3x3()
    inverted_view_matrix = view_matrix3.inverted_safe()
    view_direction = inverted_view_matrix @ pureZ
    view_direction.normalize()
    dolly_direction = view_direction * (view3d.view_distance * amount)
    view3d.view_location += dolly_direction

# TODO: rename, since pan is actually a left-righ swivle
def pan(view3d, mouseX, mouseY, amount):
    if amount == 0 or (mouseX == 0 and mouseY == 0):
        return
    pureZ = mathutils.Vector((0, 0, 1))
    mouse_vector = mathutils.Vector((mouseX, mouseY, 1))
    view_matrix3 = view3d.view_matrix.to_3x3()
    inverted_view_matrix = view_matrix3.inverted_safe()
    screen_origin = inverted_view_matrix @ pureZ
    screen_mouse = inverted_view_matrix @ mouse_vector
    orbit_vector = screen_mouse - screen_origin
    orbit_vector_scaled = orbit_vector * amount
    view3d.view_location += orbit_vector_scaled

def zoom(view3d, amount):
    if amount == 1:
        return
    view3d.view_distance *= amount
    
def ortho(view3d, axis):
    view_down_Z = mathutils.Quaternion((0, -1, 0, 0))
    view_down_Y = mathutils.Quaternion((1/math.sqrt(2), -1/math.sqrt(2), -0.0, -0.0))
    view_down_X = mathutils.Quaternion((1/math.sqrt(2), 0.0, 1/math.sqrt(2), 0.0))
    if axis == 'Z':
        view3d.view_rotation = view_down_Z
    if axis == 'Y':
        view3d.view_rotation = view_down_Y
    if axis == 'X':
        view3d.view_rotation = view_down_X
    view3d.view_perspective = 'ORTHO'
    
    
THRESHOLD = 0.02*0.02

SDL_MIN_JOYAXISMOTION = -32768
SDL_MAX_JOYAXISMOTION = 32767

def normalizeJoyAxisMotion(sdl_value):
    if -256 <= sdl_value and sdl_value <= 256:
        return 0
    elif sdl_value > 0:
        return sdl_value / SDL_MAX_JOYAXISMOTION
    elif sdl_value < 0:
        return -(sdl_value / SDL_MIN_JOYAXISMOTION)
    # This is an error
    return 0


hatmap = {
    sdl2.SDL_HAT_LEFTUP: [-1, 1],
    sdl2.SDL_HAT_UP: [0, 1],
    sdl2.SDL_HAT_RIGHTUP: [1, 1],
    sdl2.SDL_HAT_LEFT: [-1, 0],
    sdl2.SDL_HAT_CENTERED: [0, 0],
    sdl2.SDL_HAT_RIGHT: [1, 0],
    sdl2.SDL_HAT_LEFTDOWN: [-1, -1],
    sdl2.SDL_HAT_DOWN: [0, -1],
    sdl2.SDL_HAT_RIGHTDOWN: [1, -1]
}

def normalizeHat(sdl_value):
    return hatmap[sdl_value]
    


class GamepadControl:
    def reset(self):
        self.speed =[0, 0, 0, 0]
        self.speedier = 1.0
        self.roll = 0
        self.buttons = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    def __init__(self):
        self.reset()


    def get_axis_value(self, i):
        return 0
        # return (self.device.absinfo(i).value - 128) / 128
        
    def thresholdSpeed(self):
        for a in range(len(self.speed)):
            if (self.speed[a]*self.speed[a]) < THRESHOLD:
                self.speed[a] = 0
        
    def handleEvents(self):
        v3d = getActiveView3d()
        hasEvents = False
        events = sdl2.ext.get_events()
        numEvents = len(events)
        # print(" numEvents: " + str(numEvents))


        for event in events:
            # print("EVENT: " + str(event))
    
            # Joystick-related events... 
            if event.type == sdl2.SDL_JOYAXISMOTION:
                value = normalizeJoyAxisMotion(event.jaxis.value)
                if event.jaxis.axis in [1, 3]:
                    value *= -1 
                self.speed[event.jaxis.axis] = value
                
                print(f"Joystick '{event.jaxis.which}' axis '{event.jaxis.axis}' moved to '{event.jaxis.value}' = {normalizeJoyAxisMotion(event.jaxis.value)}.") 
            elif event.type == sdl2.SDL_JOYBALLMOTION: 
                # Not supported
                pass
            elif event.type == sdl2.SDL_JOYHATMOTION:
                print(f"Joystick '{event.jhat.which}' hat '{event.jhat.hat}' moved to '{event.jhat.value}'.") 
                if event.jhat.hat == 0:
                    value = normalizeHat(event.jhat.value)
                    # roll
                    self.roll = value[0]
                    
                    # change speed
                    if value[1] == 1:
                        self.speedier *= 1.1
                    if value[1] == -1:
                        self.speedier *= (1/1.1)
                    print("speedier: " + str(self.speedier))
            elif event.type == sdl2.SDL_JOYBUTTONDOWN:
                button = event.jbutton.button 
                self.buttons[button] = 1
                print(f"Joystick '{event.jbutton.which}' button '{event.jbutton.button}' down.") 
            elif event.type == sdl2.SDL_JOYBUTTONUP: 
                button = event.jbutton.button
                self.buttons[button] = 0
                if button == 0:
                    orbit(v3d, 1, 0, math.pi)
                if button == 1:
                    ortho(v3d, 'Z')
                if button == 2:
                    ortho(v3d, 'X')
                if button == 3:
                    ortho(v3d, 'Y')
                if button == 9:
                    home(v3d)
                                    
                print(f"Joystick '{event.jbutton.which}' button '{event.jbutton.button}' up.") 
                if event.jbutton.button == 11:
                    self.reset()
                    return
                
        # self.thresholdSpeed()
        
        print(str(self.speed))
        
        roll(v3d, self.roll * 0.2)
        orbit(v3d, -self.speed[1], self.speed[0], self.speedier)
        pan(v3d, self.speed[2], self.speed[3], self.speedier)
        dolly(v3d, (self.buttons[7] - self.buttons[6])*self.speedier )
        zoom(v3d, 1 + ((self.buttons[5] - self.buttons[4])*0.2))
        

#        rotation = mathutils.Euler((self.speed[0]*self.speedier*(1/3.1415), self.speed[1]*self.speedier*(1/3.1415), self.speed[2]*self.speedier*(1/3.1415))).to_quaternion()
#        getActiveView3d().view_rotation.rotate(rotation)
#        return True
    
    

gamepad_control = GamepadControl()

def main_loop():
    # print("main_loop")
    # only try again quickly if there was an event
    gamepad_control.handleEvents()
    return (1/30)

def register():
    # Initialize SDL2 for video and joystick
    sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK)
    # Open the first joystick (you can change the index if needed)
    joystick = sdl2.SDL_JoystickOpen(0)

    bpy.app.timers.register(main_loop)

def unregister():
    print("Unregister gamepad control")
    if(bpy.app.timers.is_registered(main_loop)):
        pass
    bpy.app.timers.unregister(main_loop)
    # if(bpy.app.timers.is_registered(gamepad_control.check_gamepad)):
    #     bpy.app.timers.unregister(gamepad_control.check_gamepad)
    sdl2.SDL_JoystickClose(joystick)
    sdl2.SDL_Quit()


while True:
    main_loop()
    time.sleep(1/5)