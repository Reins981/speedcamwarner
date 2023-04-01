from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.bubble import Bubble
from kivy_garden.mapview import MapMarkerPopup


class CustomMarker(MapMarkerPopup):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(on_touch_move=self.open)
        self.bind(on_touch_up=self.open)

    def open(self, *args):
        self.is_open = True
        self.refresh_open_status()

    def on_press(self, *args):
        self.is_open = False
        self.refresh_open_status()


class CustomAsyncImage(AsyncImage):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class CustomBubble(Bubble):
    def __int__(self, **kwargs):
        super.__init__(**kwargs)


class CustomLabel(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_text(self, *args):
        c_text = self.__customize_text(*args)
        self.text = c_text
        self.texture_update()

    @staticmethod
    def __customize_text(*args):
        customized_string = ""
        for arg in args:
            customized_string = "\n".join((customized_string, arg))
        return customized_string


class CustomLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
