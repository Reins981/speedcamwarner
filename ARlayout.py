from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.utils import platform
from Edgedetect import EdgeDetect


class ARLayout(FloatLayout):
    edge_detect = EdgeDetect(aspect_ratio='16:9')

    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self.sm = args[0]
        ARLayout.edge_detect.init(args[1], args[2], args[3], args[4])

    def callback_return(self):
        self.sm.current = 'Operative'


class ButtonsLayout(RelativeLayout):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if platform == 'android':
            self.normal = 'camera_icons/cellphone-screenshot_white.png'
            self.down = 'camera_icons/cellphone-screenshot_red.png'
            self.s_capture = 'camera_icons/screenshot.png'
        else:
            self.normal = 'camera_icons/monitor-screenshot_white.png'
            self.down = 'camera_icons/monitor-screenshot_red.png'
            self.s_capture = 'camera_icons/screenshot.png'

    def on_size(self, layout, size):
        if platform == 'android':
            self.ids.screen.min_state_time = 0.3
        else:
            self.ids.screen.min_state_time = 1
        if Window.width < Window.height:
            self.pos = (0, 0)
            self.size_hint = (1, 0.2)
            self.ids.other.pos_hint = {'center_x': .3, 'center_y': .5}
            self.ids.other.size_hint = (.2, None)
            self.ids.screen.pos_hint = {'center_x': .7, 'center_y': .5}
            self.ids.screen.size_hint = (.2, None)
            self.ids.connect.pos_hint = {'center_x': .9, 'center_y': .7}
            self.ids.connect.size_hint = (.2, None)
        else:
            self.pos = (Window.width * 0.8, 0)
            self.size_hint = (0.2, 1)
            self.ids.other.pos_hint = {'center_x': .5, 'center_y': .7}
            self.ids.other.size_hint = (None, .2)
            self.ids.screen.pos_hint = {'center_x': .5, 'center_y': .3}
            self.ids.screen.size_hint = (None, .2)
            self.ids.connect.pos_hint = {'center_x': .5, 'center_y': .1}
            self.ids.connect.size_hint = (None, .2)

    def callback_return(self):
        self.parent.callback_return()

    def screenshot(self):
        self.parent.edge_detect.capture_screenshot()

    def select_camera(self, facing):
        self.parent.edge_detect.select_camera(facing)

    def disconnect_camera(self):
        self.parent.edge_detect.disconnect_camera()

    def connect_camera(self, analyze_pixels_resolution=720,
                       enable_analyze_pixels=True,
                       enable_video=False):
        if self.parent.edge_detect.camera_connected:
            self.disconnect_camera()
        else:
            self.parent.edge_detect.init_ar_detection()
            self.parent.edge_detect.connect_camera(
                analyze_pixels_resolution=analyze_pixels_resolution,
                enable_analyze_pixels=enable_analyze_pixels,
                enable_video=enable_video)


Builder.load_string("""
<ARLayout>:
    edge_detect: self.ids.preview
    EdgeDetect:
        aspect_ratio: '16:9'
        id:preview
    ButtonsLayout:
        id:buttons

<ButtonsLayout>:
    normal:
    down:
    s_capture:
    Button:
        id:connect
        on_press: root.connect_camera()
        height: self.width
        width: self.height
        background_normal: root.normal
        background_down: root.down
    Button:
        id:screen
        on_press: root.screenshot()
        height: self.width
        width: self.height
        background_normal: root.s_capture
        background_down: root.s_capture
    Button:
        id:other
        on_press: root.callback_return()
        height: self.width
        width: self.height
        text: "<<<"
        bold: True
        font_size: 60
        background_color: (.5, .5, .5, .5)
""")