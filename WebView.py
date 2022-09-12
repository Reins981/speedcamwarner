import kivy
import os
from kivy.app import App
from kivy.lang import Builder
from kivy.utils import platform
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.modalview import ModalView
from kivy.clock import Clock
from jnius import autoclass, cast, PythonJavaClass, java_method
from android.runnable import run_on_ui_thread

WebViewA = autoclass('android.webkit.WebView')
WebViewClient = autoclass('android.webkit.WebViewClient')
ViewGroup = autoclass('android.view.ViewGroup')
KeyEvent = autoclass('android.view.KeyEvent')
LayoutParams = autoclass('android.view.ViewGroup$LayoutParams')
LinearLayout = autoclass('android.widget.LinearLayout')
activity = autoclass('org.kivy.android.PythonActivity').mActivity
URL = os.path.join(os.path.abspath(os.path.dirname(__file__)), "assets", "leaf.html")


class KeyListener(PythonJavaClass):
    __javacontext__ = 'app'
    __javainterfaces__ = ['android/view/View$OnKeyListener']

    def __init__(self, listener):
        super().__init__()
        self.listener = listener

    @java_method('(Landroid/view/View;ILandroid/view/KeyEvent;)Z')
    def onKey(self, v, key_code, event):
        '''if event.getAction() == KeyEvent.ACTION_DOWN and\
           key_code == KeyEvent.KEYCODE_BACK:'''
        return self.listener()


class WebView(ModalView):
    # https://developer.android.com/reference/android/webkit/WebView
    web_view = None
    layout = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.open()

    @run_on_ui_thread
    def on_open(self):
        webview = WebViewA(activity)
        wvc = WebViewClient()
        webview.setWebViewClient(wvc)
        settings = webview.getSettings()
        settings.setJavaScriptEnabled(True)
        settings.setUseWideViewPort(True)  # enables viewport html meta tags
        settings.setLoadWithOverviewMode(True)  # uses viewport
        settings.setSupportZoom(True)  # enables zoom
        settings.setBuiltInZoomControls(True)  # enables zoom controls
        settings.setAllowContentAccess(True)
        settings.setAllowFileAccess(True)
        activity.setContentView(webview)
        '''WebView.layout = LinearLayout(activity)
        WebView.layout.setOrientation(LinearLayout.VERTICAL)
        WebView.layout.addView(webview, 100, 100)
        activity.addContentView(WebView.layout, LayoutParams(-1, -1))'''
        webview.setOnKeyListener(KeyListener(self.back_pressed))
        WebView.web_view = webview
        webview.loadUrl(URL)

    @run_on_ui_thread
    def on_dismiss(self):
        if WebView.web_view is not None:
            WebView.web_view.clearHistory()
            WebView.web_view.clearCache(True)
            WebView.web_view.clearFormData()
            WebView.web_view.destroy()
            # parent = cast(ViewGroup, WebView.layout.getParent())
            # if parent is not None: parent.removeView(WebView.layout)
            WebView.layout = None
            WebView.web_view = None

    def pause(self):
        if WebView.web_view is not None:
            WebView.web_view.pauseTimers()
            WebView.web_view.onPause()

    def resume(self):
        if WebView.web_view is not None:
            WebView.web_view.onResume()
            WebView.web_view.resumeTimers()

    def close_web_view(self, force=False, animation=True):
        self.dismiss(force=force, animation=animation)

    def back_pressed(self):
        self.dismiss()
        return True




