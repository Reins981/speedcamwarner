from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.bubble import Bubble
from kivy_garden.mapview import MapMarkerPopup


class CustomMarkerBase(MapMarkerPopup):
    marker_pressed_pois = False
    marker_pressed_cams = False
    marker_pressed_constructions = False
    marker_type = "CAM"
    marker_instance = None

    def __init__(self, marker_list_pois, marker_list_cams, marker_list_constructions, **kwargs):
        super().__init__(**kwargs)
        self.marker_list_pois = marker_list_pois
        self.marker_list_cams = marker_list_cams
        self.marker_list_constructions = marker_list_constructions
        self.bind(on_touch_move=self.open)
        self.bind(on_touch_up=self.open)

    def open(self, *args):
        if self.marker_type == "CAM":
            marker_list = self.marker_list_cams
            marker_pressed = CustomMarkerBase.marker_pressed_cams
        elif self.marker_type == "POI":
            marker_list = self.marker_list_pois
            marker_pressed = CustomMarkerBase.marker_pressed_pois
        else:
            marker_list = self.marker_list_constructions
            marker_pressed = CustomMarkerBase.marker_pressed_constructions

        if marker_pressed:
            for marker in marker_list:
                if CustomMarkerBase.marker_instance is marker:
                    CustomMarkerBase.marker_instance.open_popup()
                else:
                    marker.close_popup()
        else:
            for marker in marker_list:
                marker.open_popup()

    def on_press(self, *args):
        CustomMarkerBase.marker_instance = self

        if self.marker_type == "CAM":
            marker_pressed = CustomMarkerBase.marker_pressed_cams
            if marker_pressed:
                marker_pressed = False
            else:
                marker_pressed = True
            CustomMarkerBase.marker_pressed_cams = marker_pressed
        elif self.marker_type == "POI":
            marker_pressed = CustomMarkerBase.marker_pressed_pois
            if marker_pressed:
                marker_pressed = False
            else:
                marker_pressed = True
            CustomMarkerBase.marker_pressed_pois = marker_pressed
        else:
            marker_pressed = CustomMarkerBase.marker_pressed_constructions
            if marker_pressed:
                marker_pressed = False
            else:
                marker_pressed = True
            CustomMarkerBase.marker_pressed_constructions = marker_pressed

    def close_popup(self):
        self.is_open = False
        self.refresh_open_status()

    def open_popup(self):
        self.is_open = True
        self.refresh_open_status()


class CustomMarkerPois(CustomMarkerBase):
    marker_type = "POI"


class CustomMarkerCams(CustomMarkerBase):
    marker_type = "CAM"


class CustomMarkerConstructionAreas(CustomMarkerBase):
    marker_type = "CONSTRUCTION"


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
