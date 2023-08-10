import cv2
import os
import time
from kivy.clock import mainthread
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.graphics import Color, Rectangle
import numpy as np
from camera4kivy import Preview
from Logger import Logger


class EdgeDetect(Preview):

    g = None
    main_app = None
    voice_prompt_queue = None
    cv_voice = None
    log_viewer = None
    speed_l = None
    TRIGGER_TIME_AR_SOUND_MAX = 3

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logger = Logger(self.__class__.__name__)
        self.analyzed_texture = None

        # Create an additional texture for AR overlay
        self.overlay_texture = None
        self.backup_faces = None
        self.backup_people = None
        self.freeflow = False
        self.last_ar_sound_time = 0

        self.init_ar_detection()

    ####################################
    # Analyze a Frame - NOT on UI Thread
    ####################################

    @classmethod
    def init(cls, gps, main_app, voice_queue, cv_voice, speed_l):
        cls.g = gps
        cls.main_app = main_app
        cls.voice_prompt_queue = voice_queue
        cls.cv_voice = cv_voice
        cls.speed_l = speed_l

    def set_log_viewer(self, log_viewer):
        EdgeDetect.log_viewer = log_viewer

    def init_ar_detection(self):
        BASE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data_models")
        CASCADE_FILE_FACE = os.path.join(BASE_PATH, 'haarcascade_frontalface_alt_tree.xml')
        CASCADE_FILE_FULL_BODY = os.path.join(BASE_PATH, 'haarcascade_fullbody.xml')

        self.face_cascade = cv2.CascadeClassifier()
        self.face_cascade.load(CASCADE_FILE_FACE)
        self.face_cascade.load(CASCADE_FILE_FULL_BODY)

        # Load the pre-trained HOG detector for pedestrian detection
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self.freeflow = False

    def analyze_pixels_callback(self, pixels, image_size, image_pos, scale, mirror):
        # pixels : analyze pixels (bytes)
        # image_size   : analyze pixels size (w,h)
        # image_pos    : location of Texture in Preview (due to letterbox)
        # scale  : scale from Analysis resolution to Preview resolution
        # mirror : true if Preview is mirrored

        rgba = np.fromstring(pixels, np.uint8).reshape(image_size[1],
                                                       image_size[0], 4)
        # Note, analyze_resolution changes the result. Because with a smaller
        # resolution the gradients are higher and more edges are detected.

        # ref https://likegeeks.com/python-image-processing/
        pixels = rgba.tostring()

        frame = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)

        if np.size(frame) == 0:
            self.logger.print_log_line("AR Frame is empty!", log_level="ERROR")
            return

        # Detect faces in the frame
        faces = self.detect_faces(frame)

        # Detect people in the frame
        people = self.detect_people(frame)

        results_found = self.update_results(faces, people)

        if results_found:
            self.freeflow = False
            Clock.schedule_once(lambda dt: self.speed_l.update_ar("!!!"), 0)
            current_time = time.time()
            # Avoid frequent updates due to performance
            if current_time - self.last_ar_sound_time >= EdgeDetect.TRIGGER_TIME_AR_SOUND_MAX:
                self.logger.print_log_line("AR detection successful",
                                           log_viewer=EdgeDetect.log_viewer)
                self.play_ar_sound()
                self.last_ar_sound_time = current_time

            if not self.g.camera_in_progress():
                if not self.g.camera_is_ar_human():
                    self.g.update_ar()
        else:
            Clock.schedule_once(lambda dt: self.speed_l.update_ar("OK"), 0)
            # Reset to trigger a new voice prompt
            if not self.g.camera_in_progress() and not self.freeflow:
                self.g.update_speed_camera("FREEFLOW")
                self.freeflow = True

        if results_found:
            results = [faces, people]
            for result in results:
                for (x, y, w, h) in result:
                    # Draw a red rectangle around each detected face
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 5)

        self.make_thread_safe(pixels, frame, image_size)

    @mainthread
    def make_thread_safe(self, pixels, frame, size):
        if not self.analyzed_texture or \
                self.analyzed_texture.size[0] != size[0] or \
                self.analyzed_texture.size[1] != size[1]:
            self.analyzed_texture = Texture.create(size=size, colorfmt='rgba')
            self.analyzed_texture.flip_vertical()
        if not self.overlay_texture:
            self.overlay_texture = Texture.create(size=(frame.shape[1], frame.shape[0]),
                                                  colorfmt='rgba')
            self.overlay_texture.flip_vertical()

        if self.camera_connected:
            self.analyzed_texture.blit_buffer(pixels, colorfmt='rgba')
            # Convert the frame back to Kivy texture and update the camera feed
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
            buf = frame.tobytes()
            self.overlay_texture.blit_buffer(buf, colorfmt='rgba', bufferfmt='ubyte')
        else:
            # Clear local state so no thread related ghosts on re-connect
            self.analyzed_texture = None
            self.overlay_texture = None

    ################################
    # Annotate Screen - on UI Thread
    ################################

    def canvas_instructions_callback(self, texture, tex_size, tex_pos):
        # texture : preview Texture
        # size    : preview Texture size (w,h)
        # pos     : location of Texture in Preview Widget (letterbox)
        # Add the analyzed image
        if self.analyzed_texture:
            Color(1, 1, 1, 1)
            Rectangle(texture=self.analyzed_texture,
                      size=tex_size, pos=tex_pos)

        if self.overlay_texture:
            Color(1, 1, 1, 1)
            Rectangle(texture=self.overlay_texture,
                      size=tex_size, pos=tex_pos)

    def detect_faces(self, frame):
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5)
        return faces

    def detect_people(self, frame):
        # Detect people in the frame using the HOG detector
        # Returns a list of rectangles representing the detected people
        people, _ = self.hog.detectMultiScale(frame)
        return people

    def update_results(self, faces, people):
        results_found = False
        if len(faces) > 0:
            if self.backup_faces is None or not np.array_equal(self.backup_faces, faces):
                self.backup_faces = np.copy(faces)
                results_found = True

        if len(people) > 0:
            if self.backup_people is None or not np.array_equal(self.backup_people, people):
                self.backup_people = np.copy(people)
                results_found = True

        return results_found

    def play_ar_sound(self):
        self.voice_prompt_queue.produce_ar_status(self.cv_voice, "AR_HUMAN")
