#!/usr/bin/python3

import os
import re
import time
import string
import traceback, sys
import csv
from datetime import datetime
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import QtCore

from libcamera import controls, Transform
from picamera2 import Picamera2, Preview
from picamera2.previews.qt import QGlPicamera2, QPicamera2

from pprint import *


# UTILITY CLASSES ======================================================
class WorkerSignals(QObject):
    ''' The signals available from a running worker thread.
    
    https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/

    Attributes
    ----------
    finished: pyqtSignal
        No data
    error : pyqtSignal
        tuple (exctype, value, traceback.format_exc())
    result : pyqtSignal
        object data returned from processing, anything
    progress : pyqtSignal
        int indicating % progress
    '''
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)

class Worker(QRunnable):
    ''' Worker thread
    
    https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/

    Inherits from QRunnable to handler worker thread setup, signals and
    wrap-up.
    
    Parameters
    ----------
    fn: function
        The function callback to run on this worker thread. Supplied
        args and kwargs will be passed through to the runner.
    args
        Arguments to pass to the callback function
    kwargs
        Keyword arguments to pass to the callback function
    '''
    
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        
        # Add the callback to our kwargs
        # self.kwargs['progress_callback'] = self.signals.progress

    @pyqtSlot()
    def run(self):
        ''' Initialise the runner function with passed args, kwargs. '''
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

class Default():
    file_ext = ".png"
    basename = "Unnamed"
    save_dir = "/run/user/" +str(os.getuid())+  "/gvfs/smb-share:server=arc.auburn.edu,share=lab/specgen/ImageCapture/Data" #None
    operator = None
    initials = None
    exp_id = 1
    brood_id = "A"
    width = 2592 # sensor: 2592x1944-pgAA (5MP)
    height = 1944

class PicPath(QObject):
    ''' A class representing the names and paths of image files
    
    Static variables store the current file path information that will 
    assigned to the next photo taken
    
    Parameters
    ----------
    basename : str
        Name of the file without the path or extension (default = `default_basename`)
    fileext : str
        File extension (default = `default_fileext`)
    in_dir :str 
        String representing the path to the output directory (default = `current_dir`)
    
    Attributes
    ----------
    filepathChanged : pyqtSignal
        str of new filepath
    '''
    
    # Define new signals available from a PicPath object
    filepathChanged = pyqtSignal(str)
    
    # Static variables shared between all instances of PicPath
    # Access with PicPath.variable
    uid = os.getuid()
    today = datetime.now().strftime("%Y-%m-%d")
    script_dir = os.path.dirname(os.path.realpath(__file__))
    print(script_dir)
    settings = QSettings("Auburn University", "ImCapp")
    
    save_dir = settings.value("save_dir") if settings.value("save_dir") else Default.save_dir
    if not os.path.isdir(save_dir):
        save_dir = script_dir
    
    default_fileext = settings.value("file_ext") if settings.value("file_ext") else Default.file_ext
    default_basename = settings.value("basename") if settings.value("basename") else Default.basename
    default_filename = default_basename + default_fileext
    current_filepath = os.path.join(os.path.sep, save_dir, default_filename)
    # current_prettypath = current_filepath
    
    def __init__(self, initials, exp_id = None, batch_id = None, basename = default_basename,
                 fileext = default_fileext, in_dir = save_dir):
        super().__init__()
        # folder_id = "_".join([PicPath.today, initials, prefix])
        
        self._basename = basename
        self._fileext = fileext
        self._filename = self._basename + self._fileext
        self._directory = os.path.join(os.path.sep, in_dir, initials, exp_id, batch_id + "_" + PicPath.today)
        self._filepath = os.path.join(os.path.sep, self._directory, self._filename)
        # self.prettypath = self.make_filepath_pretty1()
        
        # if not os.path.isdir(self._directory):
            # os.makedirs(self._directory)
        
        if self.basename == PicPath.default_basename:
            unique = self.make_filepath_unique()
            self.directory, tail = os.path.split(unique)
            self.basename, self.fileext = os.path.splitext(tail)
            PicPath.default_basename = self.basename
            PicPath.default_filename = self.filename
    
    def update(self, initials, exp_id = None, batch_id = None, basename = default_basename,
                 fileext = default_fileext, in_dir = save_dir):
        self._basename = basename
        self._fileext = fileext
        self._filename = self._basename + self._fileext
        self._directory = os.path.join(os.path.sep, in_dir, initials, exp_id, batch_id + "_" + PicPath.today)
        self._filepath = os.path.join(os.path.sep, self._directory, self._filename)
        
        if not os.path.isdir(self._directory):
            os.makedirs(self._directory)
        
        if self.basename == PicPath.default_basename:
            unique = self.make_filepath_unique()
            self.directory, tail = os.path.split(unique)
            self.basename, self.fileext = os.path.splitext(tail)
            PicPath.default_basename = self.basename
            PicPath.default_filename = self.filename
    
    def make_filepath_pretty(value):
        smb_match = re.search("/gvfs/smb-share:server=(.*),share=(.*)", value)
        if smb_match:
            return "smb://" + "/".join(smb_match.group(1,2))
        else:
            return value
    
    def make_filepath_pretty1(self):
        smb_match = re.search("/gvfs/smb-share:server=(.*),share=(.*)", self.filepath)
        if smb_match:
            return "smb://" + "/".join(smb_match.group(1,2))
        else:
            return self.filepath
        
    # def check_picture_exists():
    #     return os.path.exists(PicPath.current_filepath)

    def make_filepath_unique(self):
        path = self.filepath
        if not os.path.exists(path):
            return path
        
        head, tail = os.path.split(path)
        basename, extension = os.path.splitext(tail)
        group_match = re.match("(.*)(?=\((?P<num>[0-9]+)\))", basename)
        
        if not group_match:
            print("No regex match")
            num = 1
        
        if group_match:
            print("Found a regex match")
            basename = group_match.group(1)
            num = int(group_match.group("num"))
            path = basename + "(" + str(num) + ")" + extension
        
        filename = basename + "(" + str(num) + ")" + extension
        path = os.path.join(os.path.sep, head, filename)
        
        while os.path.exists(path):
            filename = basename + "(" + str(num) + ")" + extension
            path = os.path.join(os.path.sep, head, filename)
            num += 1
        
        self.filepath = path
        return path
    
    # GETTERS AND SETTERS ==============================================
    @property
    def basename(self):
        return self._basename

    @basename.setter
    def basename(self, value):
        self._basename = value
        self.filename =  value + self.fileext

    @property
    def fileext(self):
        return self._fileext

    @fileext.setter
    def fileext(self, value):
        self._fileext = value
        self.filename = self.basename + value

    @property
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, value):
        self._filename = value
        PicPath.current_filename = value
        self.filepath = os.path.join(os.path.sep, self.directory, value)
    
    @property
    def directory(self):
        return self._directory
    
    @directory.setter
    def directory(self, value):
        self._directory = value
        self.filepath = os.path.join(os.path.sep, value, self.filename)
    
    @property
    def filepath(self):
        return self._filepath

    @filepath.setter
    def filepath(self, value):
        self._filepath = value
        PicPath.current_filepath = value
        self.filepathChanged.emit(value)


# GUI WIDGETS ==========================================================
class MainWindow(QMainWindow):
    ''' Set up a display window for the GUI.
    
    Parameters
    ----------
    camera : Picamera2()
    args : type
    kwargs : type
    
    Attributes
    ----------
    current_vial_num : type
    current_picpath : type
    container : type
    manage_vials_widget : ManageVialsWidget()
    manage_camera_widget : ManageCameraWidget(camera)
    '''
    
    def __init__(self, camera, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = QSettings("Auburn University", "ImCapp")
        self.check_defaults()
        self.load_settings()
        
        start_dlg = StartUpDialog(self)
        if not start_dlg.exec():
            print("User canceled start-up")
            raise SystemExit
        
        self.filepath_found = False
        
        # self._operator = start_dlg.options_widget.userLineEdit.text()
        self._initials = start_dlg.options_widget.initialsLineEdit.text().upper()
        self._exp_id = start_dlg.options_widget.experimentSpinBox.text()
        self._brood_id = start_dlg.options_widget.broodSpinBox.text()
        self.folder_id = self.exp_id + self.brood_id
        self.prefix = self.folder_id
        
        # self.vial_list = []
        # self.low = None
        # self.high = None

        self.current_vial_num = None
        self.current_picpath = PicPath(self.initials, self.exp_id, self.brood_id)
        self.current_picpath.filepathChanged.connect(self.update_filename)
        
        # Make a new composite widget to use as the main widget for the
        # window and set its layout to a new layout that will add
        # widgets horizontally from left to right
        self.container = QWidget()
        self.setCentralWidget(self.container)
        layout = QHBoxLayout(self.container)
        
        # Make a menu bar and add it to the MainWindow
        self.make_menubar()
        
        # Set window display settings
        self.setWindowTitle("ImCapp")
        self.resize(1000, 600) # Size for when window is not maximized
        self.setWindowState(QtCore.Qt.WindowMaximized)
        
        # Create widget objects for the left and right panes using the
        # custom widgets for managing the list of vials and the camera 
        self.manage_vials_widget = ManageVialsWidget()
        try:
            self.camera_preview = CameraPreviewWidget(camera, self.width, self.height)
            af_available = True if "AfMode" in camera.camera_controls else False
        except:
            self.camera_preview = PreviewPlaceholderWidget()
            af_available = False
            
        self.manage_camera_widget = CameraControls(self.camera_preview)
        
        self.manage_camera_widget.capture_button.clicked.connect(self.check_filepath)
        self.camera_preview.picTaken.connect(self.advance)
        
        self.manage_vials_widget.vialSelected.connect(self.on_vial_selected)
        self.manage_vials_widget.list_controls.deselect_button.clicked.connect(self.reset_filename)
        self.manage_vials_widget.list_controls.create_list_button.clicked.connect(self.do_vial_list_dlg)
        self.manage_vials_widget.list_controls.save_list_button.clicked.connect(self.save_vial_list)
        
        # Add widgets to the window's layout so they display when the 
        # window is loaded
        layout.addWidget(self.manage_vials_widget, 20)
        layout.addWidget(self.manage_camera_widget, 70)
        
        # self.camera_preview.setSizePolicy(
            # QSizePolicy.Fixed,
            # QSizePolicy.Fixed)
        # self.camera_preview.setMinimumSize(427, 324)
        # self.camera_preview.setMaximumSize(self.width, self.height)
        # self.camera_preview.setSizeIncrement(4, 3)
        # self.camera_preview.
        # print(self.camera_preview.sizeHint())
        
        if af_available:
            print(camera.camera_controls["AfMode"])
        else:
            self.manage_camera_widget.af_controls.hide()
    
    @pyqtSlot(str)
    def on_vial_selected(self, new_basename):
        self.current_picpath.basename = new_basename
        self.current_picpath.make_filepath_unique()
    
    @pyqtSlot(str)
    def on_fileext_change(self, new_ext):
        self.current_picpath.fileext = new_ext
        
    @pyqtSlot()
    def advance(self):
        self.update_filename()
            
    @pyqtSlot()
    def update_filename(self):
        self.current_picpath.make_filepath_unique()
        self.manage_camera_widget.filename_label.setText("The file will be named:\n" + PicPath.make_filepath_pretty(PicPath.current_filepath))
    
    @pyqtSlot()
    def reset_filename(self):
        self.current_picpath.basename = PicPath.default_basename
    
    @pyqtSlot()
    def check_filepath(self):
        ''' Make sure directory exists. '''
        if not self.filepath_found:
            if not os.path.isdir(self.current_picpath.directory):
                os.makedirs(self.current_picpath.directory)
            self.filepath_found = True
            
    @pyqtSlot()
    def enable_GUI(self):
        ''' Enable GUI buttons. '''
        self.capture_button.setEnabled(True)
        self.af_controls.checkbox.setEnabled(True)
        self.af_controls.button.setEnabled(True)
        # self.manage_vials_widget.list_controls.deselect_button.setEnabled(True)
        # self.manage_vials_widget.list_controls.create_list_button.setEnabled(True)
        # self.manage_vials_widget.list_controls.save_list_button.setEnabled(True)
        
    @pyqtSlot()
    def disable_GUI(self):
        ''' Disable GUI buttons. '''
        self.capture_button.setEnabled(False)
        self.af_controls.checkbox.setEnabled(False)
        self.af_controls.button.setEnabled(False)
    
    def make_menubar(self):
        # toolbar = QToolBar("Toolbar test")
        # self.addToolBar(toolbar)
        self.setStatusBar(QStatusBar(self))
        menu = self.menuBar()
        
        act_choose_dir = QAction("Choose save folder", self)
        act_choose_dir.setStatusTip("Choose a destination folder for pictures")
        act_choose_dir.triggered.connect(self.pick_directory)
        
        act_make_list = QAction("Generate vial list", self)
        act_make_list.triggered.connect(self.do_vial_list_dlg)
        
        act_settings = QAction("Settings", self)
        act_settings.triggered.connect(self.do_settings_dlg)
        
        act_defaults = QAction("Defaults", self)
        act_defaults.triggered.connect(self.do_defaults_dlg)
        
        file_menu = menu.addMenu("&File")
        file_menu.addAction(act_choose_dir)
        file_menu.addAction(act_make_list)
        
        file_menu = menu.addMenu("&Vials")
        
        file_menu = menu.addMenu("&Options")
        file_menu.addAction(act_settings)
        file_menu.addAction(act_defaults)
    
    @pyqtSlot()
    def pick_directory(self):
        chosen_dir = QFileDialog.getExistingDirectory()
        self.current_picpath.directory = chosen_dir
    
    @pyqtSlot()
    def do_vial_list_dlg(self):
        vial_list_dlg = MakeVialListDialog(self.prefix)
        if vial_list_dlg.exec():
            # self.low = vial_list_dlg.lowestSpinBox.text()
            # self.high = vial_list_dlg.highestSpinBox.text()
            self.prefix = vial_list_dlg.prefixLineEdit.text()
            [self.manage_vials_widget.add_vial_unique(vial) for vial in self.make_vial_list(vial_list_dlg.lowestSpinBox.text(), vial_list_dlg.highestSpinBox.text(), vial_list_dlg.prefixLineEdit.text())]
            if vial_list_dlg.if_save.isChecked():
                self.save_vial_list()
    
    @pyqtSlot()
    def do_settings_dlg(self):
        settings_dlg = SettingsDialog().open()
        self.load_settings()
    
    @pyqtSlot()
    def do_defaults_dlg(self):
        settings_dlg = SettingsDialog()
        settings_dlg.tabs.setCurrentWidget(settings_dlg.defaults_tab)
        settings_dlg.open()
        self.load_settings()
        
    def make_vial_list(self, low, high, prefix = None):
        return [f'{self.prefix}{i:03}' for i in range(int(low), int(high)+1)]
    
    @pyqtSlot()
    def save_vial_list(self):
        list_file = os.path.join(os.path.sep, self.current_picpath.directory, "vial_list.csv") #TODO: use Default
        print([self.manage_vials_widget.vial_list.item(i).text() for i in range(0, self.manage_vials_widget.vial_list.count())])
        with open(list_file, "w") as csv:
            csv.write('ID\n')
            size = self.manage_vials_widget.vial_list.count()-1
            for i in range(0, size):
                csv.write(self.manage_vials_widget.vial_list.item(i).text() + '\n')
            csv.write(self.manage_vials_widget.vial_list.item(size).text())
    
    def closeEvent(self, event):
        self.save_settings()
        self.check_list_status()
        super().closeEvent(event)
    
    def check_defaults(self):
        if not self.settings.value("file_ext"):
            self.settings.setValue("file_ext", Default.file_ext)
        if not self.settings.value("basename"):
            self.settings.setValue("basename", Default.basename)
        if not self.settings.value("save_dir"):
            # save_dir = QFileDialog.getExistingDirectory()
            # self.current_picpath.directory = save_dir
            self.settings.setValue("save_dir", Default.save_dir)
        if not self.settings.value("operator"):
            self.settings.setValue("operator", Default.operator)
        if not self.settings.value("initials"):
            self.settings.setValue("initials", Default.initials)
        if not self.settings.value("exp_id"):
            self.settings.setValue("exp_id", Default.exp_id)
        if not self.settings.value("brood_id"):
            self.settings.setValue("brood_id", Default.brood_id)
        if not self.settings.value("width"):
            self.settings.setValue("width", Default.width)
        if not self.settings.value("height"):
            self.settings.setValue("height", Default.height)
            
    def load_settings(self):
        # self.operator = self.settings.value("operator")
        self.initials = self.settings.value("initials")
        self.exp_id = self.settings.value("exp_id")
        self.brood_id = self.settings.value("brood_id")
        self.width = self.settings.value("width")
        self.height = self.settings.value("height")
        
        try:
            self.current_picpath.update(self.initials, self.exp_id, self.brood_id)
        except:
            pass
        
    def save_settings(self):
        # self.settings.setValue("operator", self.operator)
        self.settings.setValue("initials", self.initials)
        self.settings.setValue("exp_id", self.exp_id)
        self.settings.setValue("brood_id", self.brood_id)
    
    def check_list_status(self):
        pass
        
    @property
    def operator(self):
        return self._operator

    @operator.setter
    def operator(self, value):
        self._operator = value

    @property
    def initials(self):
        return self._initials

    @initials.setter
    def initials(self, value):
        self._initials = value

    @property
    def exp_id(self):
        return self._exp_id

    @exp_id.setter
    def exp_id(self, value):
        self._exp_id = value

    @property
    def brood_id(self):
        return self._brood_id

    @brood_id.setter
    def brood_id(self, value):
        self._brood_id = value

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self._width = int(value)
        
    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        self._height = int(value)
        

# CAMERA WIDGETS =======================================================
class CameraControls(QWidget):
    def __init__(self, preview):
        super().__init__()
        
        self.preview = preview
        self.cam = preview.cam
        self.picam2 = preview.picam2
        self.af_controls = AFControlsWidget()
        self.capture_button = QPushButton("Take picture")
        self.filename_label = QLabel("The file will be named:\n" + PicPath.make_filepath_pretty(PicPath.current_filepath))
        
        # Add the component widgets to the layout in order from top to
        # bottom using integers to define stretch to improve sizing
        layout = QVBoxLayout(self)
        layout.addWidget(self.cam, 80)
        layout.addWidget(self.af_controls, 10)
        layout.addWidget(self.capture_button, 10)
        layout.addWidget(self.filename_label, 5)
        
        # Set whether autofocus needs to be performed before each image
        # capture based on whether the AFControls checkbox is checked
        self.af_required = self.af_controls.checkbox.isChecked()
        
        # Link controls to functions that define what to do
        self.af_controls.button.clicked.connect(self.run_af_once)
        self.af_controls.checkbox.stateChanged.connect(self.af_requirement_changed)
        self.capture_button.clicked.connect(self.capture_button_clicked)
    
    @pyqtSlot()
    def capture_button_clicked(self):
        ''' Respond to image capture button being clicked. '''
        # Disable GUI elements until image capture is complete
        self.disable_GUI()
        
        # Check if autofocus must be performed before image is taken
        if self.af_required == True:
            # Set up a thread to run autofocus
            af_worker = Worker(self.run_af)
            # TODO: if fail, run again -- worker.signals.result.connect(self.print_output)
            # Link completion of autofocus thread to image capture function
            af_worker.signals.finished.connect(self.do_capture)
            # Start autofocus Worker thread, which will start image
            # capture when autofocus is finished
            QThreadPool.globalInstance().start(af_worker)
        else:
            # Start taking picture immediately since not doing autofocus
            self.do_capture()
    
    @pyqtSlot()
    def run_af(self):
        self.picam2.autofocus_cycle(self.cam)
    
    @pyqtSlot()
    def run_af_once(self):
        self.disable_GUI()
        # Set up a thread to run autofocus
        af_worker = Worker(self.run_af)
        # TODO: if fail, run again -- worker.signals.result.connect(self.print_output)
        # Link completion of autofocus thread to enabling GUI
        af_worker.signals.finished.connect(self.enable_GUI)
        # Start autofocus Worker thread
        QThreadPool.globalInstance().start(af_worker)
    
    def af_requirement_changed(self):
        self.af_required = self.af_controls.checkbox.isChecked()


class PreviewPlaceholderWidget(QWidget):
    '''
    Placeholder widget to display camera if camera is not found.
    
    Attributes
    ----------
    picTaken : pyqtSignal
    '''
    picTaken = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor('cyan'))
        self.setPalette(palette)
        
        self.cam = self
        self.picam2 = None
    
    @pyqtSlot()
    def do_capture(self):
        print("Cannot take picture without camera")

class CameraPreviewWidget(QWidget):
    '''
    Display camera buffer as preview.
    
    Attributes
    ----------
    picTaken : pyqtSignal
    '''
    picTaken = pyqtSignal()
    
    def __init__(self, camera, width, height):
        super().__init__()
        
        self.picam2 = camera
        
        if not self.picam2:
            raise Exception
        
        self.picam2.options["quality"] = 95 # JPEG quality 0: lowest -> 95: highest
        self.picam2.options["compress_level"] = 0 # PNG compression 0: none -> 9: most

        # Transform(hflip=1, vflip=1)
        self.preview_config = self.picam2.create_preview_configuration(main={"size": (width, height)})
        self.capture_config = self.picam2.create_still_configuration(main={"size": (width, height)})

        self.picam2.configure(self.preview_config)
        # self.cam = QGlPicamera2(self.picam2, width=width, height=height, keep_ar=True)
        self.cam = QPicamera2(self.picam2, width=width, height=height, keep_ar=True)
        self.picam2.start()
        self.cam.done_signal.connect(self.capture_pic)

    @pyqtSlot()
    def do_capture(self):
        print("Starting image capture for:", PicPath.current_filepath)
        self.picam2.capture_file(
            PicPath.current_filepath,
            wait = False,
            signal_function = self.cam.signal_done)
    
    # @pyqtSlot(picamera2.job.Job)
    def capture_pic(self, job):
        print("Executing capture_pic")
        print(type(job))
        self.picam2.wait(job)
        self.enable_GUI()
        print("Picture saved as %s" % (PicPath.current_filepath))
        self.picTaken.emit()

class AFControlsWidget(QWidget):
    ''' A widget containing the widgets that control autofocus. '''

    def __init__(self):
        super().__init__()
        
        layout = QHBoxLayout(self)
        
        self.checkbox = QCheckBox("Run autofocus before each picture")
        self.button = QPushButton("Run autofocus now")
        
        layout.addWidget(self.checkbox, 10)
        layout.addWidget(self.button, 5)
        
        self.checkbox.setCheckState(Qt.Unchecked)



# VIAL LIST WIDGETS ====================================================
class ManageVialsWidget(QWidget):
    '''
    A composite widget that contains the widgets that manage the list of
    vials being imaged.
    
    Widgets included:
    - vial_list
    - list_controls
    
    Attributes
    ----------
    vialSelected : pyqtSignal
    '''
    vialSelected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        self.layout = QVBoxLayout(self)
        
        # self.nav_buttons = QGroupBox()
        # vial_arrows_layout = QHBoxLayout(self.nav_buttons)
        self.vial_arrow_prev = QPushButton('<- Previous')
        self.vial_arrow_next = QPushButton('Next ->')
        self.vial_arrow_prev.setEnabled(False)
        self.vial_arrow_next.setEnabled(False)
        
        vial_arrows_layout = QHBoxLayout()
        vial_arrows_layout.addWidget(self.vial_arrow_prev)
        vial_arrows_layout.addWidget(self.vial_arrow_next)
        
        self.vial_list = QListWidget()
        self.list_controls = VialListControlWidget()

        self.vial_list.currentItemChanged.connect(self.index_changed)
        self.vialSelected.connect(self.on_vial_selected)
        
        self.list_controls.add_from_file_button.clicked.connect(self.pick_file)
        # self.list_controls.create_list_button.clicked.connect(self.)
        self.list_controls.deselect_button.clicked.connect(self.deselect)        
        self.list_controls.clear_list_button.clicked.connect(self.clear_vial_list)

        self.vial_arrow_prev.clicked.connect(self.prev_vial)
        self.vial_arrow_next.clicked.connect(self.next_vial)

        self.layout.addWidget(self.list_controls)
        self.layout.addWidget(self.vial_list, 80)
        # self.layout.addWidget(self.nav_buttons)
        self.layout.addLayout(vial_arrows_layout)
    
    # def disable_nav_buttons(self):
        # self.vial_arrow_prev.setEnabled(False)
        # self.vial_arrow_next.setEnabled(False)

    # def enable_nav_buttons(self):
        # self.vial_arrow_prev.setEnabled(True)
        # self.vial_arrow_next.setEnabled(True)
    

    @pyqtSlot(QListWidgetItem)
    def index_changed(self, item):
        # print("Vial selected: " + item.text())
        self.vialSelected.emit("vial" + item.text())
    
    @pyqtSlot()
    def prev_vial(self):
        self.vial_list.setCurrentRow(self.vial_list.currentRow()-1)
        
    @pyqtSlot()
    def next_vial(self):
        self.vial_list.setCurrentRow(self.vial_list.currentRow()+1)
        
    @pyqtSlot()
    def add_vial(self):
        if (self.vial_add.input.hasAcceptableInput()):
            self.add_vial_unique(self.vial_add.input.displayText())
            
    @pyqtSlot()
    def add_vial_unique(self, user_input):
        vials = [i.text() for i in self.vial_list.findItems(user_input, QtCore.Qt.MatchExactly)]
        if user_input not in vials:
            self.list_controls.clear_list_button.setEnabled(True)
            self.list_controls.save_list_button.setEnabled(True)
            self.vial_list.addItem(user_input)
            
    @pyqtSlot()
    def on_vial_selected(self):
        self.list_controls.deselect_button.setEnabled(True)
        if self.vial_list.currentRow() > 0:
            self.vial_arrow_prev.setEnabled(True)
        else:
            self.vial_arrow_prev.setEnabled(False)
        if self.vial_list.currentRow() < self.vial_list.count()-1:
            self.vial_arrow_next.setEnabled(True)
        else:
            self.vial_arrow_next.setEnabled(False)
        
    @pyqtSlot()
    def deselect(self):
        self.vial_list.currentItem().setSelected(False)
        self.list_controls.deselect_button.setEnabled(False)
    
    @pyqtSlot()
    def clear_vial_list(self):
        confirm_button = QMessageBox.question(
            self,
            "Are you sure?",
            "Do you want to remove all vials from the list?")
        
        if confirm_button == QMessageBox.StandardButton.Yes:
            self.list_controls.clear_list_button.setEnabled(False)
            self.list_controls.save_list_button.setEnabled(False)
            self.vial_list.clear()
    
    @pyqtSlot()
    def pick_file(self):
        csvfile = QFileDialog.getOpenFileName(self, "Open File", "", "Text files (*.txt *.csv)")[0]
        print("Loading vials from file:", csvfile)
        vials_to_add = self.read_vial_csv(csvfile)
        [self.add_vial_unique(vial) for vial in vials_to_add]
    
    def read_vial_csv(self, filename):
        vials = []
        try:
            with open(filename, "r", newline='') as f:
                reader = csv.reader(f)
                line1 = next(reader)
                if not line1[0].lower().startswith("vial"):
                    if not line1[0].lower().startswith("id"):
                        vials.append(line1[0])
                for row in reader:
                    vials.append(row[0])
        finally:
            return vials
        
class VialListControlWidget(QGroupBox):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.setTitle('Options')
        
        layout = QGridLayout(self)
        
        self.add_from_file_button = QPushButton("Add vials from file")
        self.clear_list_button = QPushButton("Clear vial list")
        self.save_list_button = QPushButton("Save vial list")
        self.deselect_button = QPushButton("Deselect")
        self.create_list_button = QPushButton("Generate vial list")
        
        self.clear_list_button.setEnabled(False)
        self.save_list_button.setEnabled(False)
        self.deselect_button.setEnabled(False)
        
        layout.addWidget(self.add_from_file_button)
        layout.addWidget(self.create_list_button)
        layout.addWidget(self.save_list_button)
        layout.addWidget(self.clear_list_button)
        layout.addWidget(self.deselect_button)
        

# CUSTOM WIDGETS =======================================================
class CharSpinBox(QSpinBox):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.letters = string.ascii_uppercase
        self.setRange(0, 25)
        self.setWrapping(True)
        
    def textFromValue(self, value):
        return self.letters[value]
    
    def validate(self, text, pos):
        v = QRegExpValidator()
        v.setRegExp(QRegExp("[a-zA-Z]"))
        return v.validate(text, pos)
        
    def valueFromText(self, text):
        text = text.upper()
        if text in self.letters:
            return self.letters.index(text)
        else:
            return 0
    
    def setValue(self, value):
        if isinstance(value, int):
            super().setValue(value)
        else:
            super().setValue(self.valueFromText(value))

class SettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("Auburn University", "ImCapp")
        layout = QHBoxLayout()
        
        self.load_defaults_button = QPushButton("Use Defaults")
        self.save_defaults_button = QPushButton("Save as Defaults")
        self.change_defaults_button = QPushButton("Change Defaults")
        
        # self.userLineEdit = QLineEdit()
        # user_validator = QRegExpValidator()
        # user_validator.setRegExp(QRegExp("[a-zA-Z]+"))
        # self.userLineEdit.setValidator(user_validator)
        
        self.initialsLineEdit = QLineEdit()
        initials_validator = QRegExpValidator()
        initials_validator.setRegExp(QRegExp("[a-zA-Z]{2,3}"))
        self.initialsLineEdit.setValidator(initials_validator)
        
        self.experimentSpinBox = QSpinBox()
        self.experimentSpinBox.setValue(1)
        self.experimentSpinBox.setWrapping(True)
        
        self.broodSpinBox = CharSpinBox()
        
        form_layout = QFormLayout()
        # form_layout.addRow(self.tr("Operator:"), self.userLineEdit)
        form_layout.addRow(self.tr("Initials:"), self.initialsLineEdit)
        form_layout.addRow(self.tr("Experiment number:"), self.experimentSpinBox)
        form_layout.addRow(self.tr("Brood ID:"), self.broodSpinBox)
        
        buttons_layout = QVBoxLayout()
        buttons_layout.addWidget(self.load_defaults_button)
        buttons_layout.addWidget(self.save_defaults_button)
        buttons_layout.addWidget(self.change_defaults_button)
        
        layout.addLayout(form_layout)
        layout.addSpacing(10)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        self.load_defaults()
        # self.validate_inputs()
        
        # self.userLineEdit.textChanged.connect(self.validate_inputs)
        self.initialsLineEdit.textChanged.connect(self.validate_inputs)
        self.change_defaults_button.clicked.connect(self.change_defaults)
        self.load_defaults_button.clicked.connect(self.load_defaults)
        self.save_defaults_button.clicked.connect(self.save_new_defaults)
    
    def validate_inputs(self):
        if self.initialsLineEdit.hasAcceptableInput(): # & self.userLineEdit.hasAcceptableInput()
            pass
    
    def change_defaults(self):
        defaults_dlg = DefaultsDialog(parent=self)
    
    def load_defaults(self):
        # self.userLineEdit.setText(self.settings.value("operator"))
        self.initialsLineEdit.setText(self.settings.value("initials"))
        self.experimentSpinBox.setValue(int(self.settings.value("exp_id")))
        self.broodSpinBox.setValue(self.settings.value("brood_id"))
    
    def reset_to_defaults(self):
        # self.userLineEdit.setText(Default.operator)
        self.initialsLineEdit.setText(Default.initials)
        self.experimentSpinBox.setValue(Default.exp_id)
        self.broodSpinBox.setValue(Default.brood_id)
    
    def save_new_defaults(self):
        # self.settings.setValue("operator", self.userLineEdit.text())
        self.settings.setValue("initials", self.initialsLineEdit.text().upper())
        self.settings.setValue("exp_id", self.experimentSpinBox.text())
        self.settings.setValue("brood_id", self.broodSpinBox.text())

    @property
    def settings(self):
        return self._settings

    @settings.setter
    def settings(self, value):
        self._settings = value
        
    @property
    def ok_button(self):
        return self._ok_button

    @ok_button.setter
    def ok_button(self, value):
        self._ok_button = value
        
    @property
    def change_defaults_button(self):
        return self._change_defaults_button
    
    @change_defaults_button.setter
    def change_defaults_button(self, value):
        self._change_defaults_button = value
    
    @property
    def save_defaults_button(self):
        return self._save_defaults_button
    
    @save_defaults_button.setter
    def save_defaults_button(self, value):
        self._save_defaults_button = value
        
    @property
    def load_defaults_button(self):
        return self._load_defaults_button
    
    @load_defaults_button.setter
    def load_defaults_button(self, value):
        self._load_defaults_button = value

    @property
    def userLineEdit(self):
        return self._userLineEdit
    
    @userLineEdit.setter
    def userLineEdit(self, value):
        self._userLineEdit = value
        
    @property
    def initialsLineEdit(self):
        return self._initialsLineEdit
    
    @initialsLineEdit.setter
    def initialsLineEdit(self, value):
        self._initialsLineEdit = value

class DefaultsWidget(SettingsWidget):
    def __init__(self):
        super().__init__()
        # user_validator = QRegExpValidator()
        # user_validator.setRegExp(QRegExp("([a-zA-Z]+)?"))
        # super().userLineEdit.setValidator(user_validator)
        
        initials_validator = QRegExpValidator()
        initials_validator.setRegExp(QRegExp("([a-zA-Z]{2,3})?"))
        super().initialsLineEdit.setValidator(initials_validator)
        
        super().change_defaults_button.hide()
        super().save_defaults_button.hide()
        super().load_defaults_button.setText("Reset Defaults")
        super().load_defaults_button.clicked.connect(super().reset_to_defaults)


# DIALOGS ==============================================================
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__()
        buttons = QDialogButtonBox.Save | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        self.button_box = QDialogButtonBox(buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        self.save_button = self.button_box.button(QDialogButtonBox.Save)
        
        self.tabs = QTabWidget()
        self.tabs.setTabBarAutoHide(True)
        self.tabs.setTabPosition(QTabWidget.West)
        
        self.settings_tab = SettingsWidget()
        self.defaults_tab = DefaultsWidget()
        
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.defaults_tab, "Defaults")
        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        layout.addWidget(self.button_box)
        self.setLayout(layout)
        
        # self.settings_tab.userLineEdit.textChanged.connect(self.validate_inputs)
        self.settings_tab.initialsLineEdit.textChanged.connect(self.validate_inputs)
        self.settings_tab.change_defaults_button.clicked.disconnect()
        self.settings_tab.change_defaults_button.clicked.connect(self.select_defaults_tab)
        self.defaults_tab.userLineEdit.textChanged.connect(self.validate_inputs)
        self.defaults_tab.initialsLineEdit.textChanged.connect(self.validate_inputs)
        self.tabs.currentChanged.connect(self.validate_inputs)
        
    def open(self):
        self.exec()
    
    def open_settings(self):
        self.hide_all_tabs()
        self.settings_tab.show()
        self.exec()
    
    def open_defaults(self):
        self.hide_all_tabs()
        self.defaults_tab.show()
        self.exec()
    
    def hide_all_tabs(self):
        for i in range(1, self.tabs.count()):
            self.tabs.widget(i).hide()
    
    def select_defaults_tab(self):
        self.tabs.setCurrentWidget(self.defaults_tab)
    
    def validate_inputs(self):
        if self.tabs.currentWidget().initialsLineEdit.hasAcceptableInput(): # & self.tabs.currentWidget().userLineEdit.hasAcceptableInput()
            self.save_button.setEnabled(True)
        else:
            self.save_button.setEnabled(False)
        
class StartUpDialog(QDialog):    
    def __init__(self, parent=None):
        super().__init__()
        self.setWindowTitle("Starting ImCapp")
        self.settings = QSettings("Auburn University", "ImCapp")
        layout = QVBoxLayout()
        
        buttons = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        self.button_box = QDialogButtonBox(buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        self.ok_button = self.button_box.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)
        
        self.options_widget = SettingsWidget()
        
        layout.addWidget(self.options_widget)
        layout.addWidget(self.button_box)
        self.setLayout(layout)
        self.validate_inputs()
        
        # self.options_widget.userLineEdit.textChanged.connect(self.validate_inputs)
        self.options_widget.initialsLineEdit.textChanged.connect(self.validate_inputs)
    
    def validate_inputs(self):
        if self.options_widget.initialsLineEdit.hasAcceptableInput(): # & self.options_widget.userLineEdit.hasAcceptableInput()
            self.ok_button.setEnabled(True)
        else:
            self.ok_button.setEnabled(False)
       
class DefaultsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__()
        self.setWindowTitle("Change Defaults")
        self.settings = QSettings("Auburn University", "ImCapp")
        layout = QVBoxLayout()
        
        buttons = QDialogButtonBox.Save | QDialogButtonBox.Cancel
        self.button_box = QDialogButtonBox(buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        self.save_button = self.button_box.button(QDialogButtonBox.Save)
        self.save_button.setEnabled(False)
        
        self.defaults_widget = DefaultsWidget()
        layout.addWidget(self.defaults_widget)
        layout.addWidget(self.button_box)
        self.setLayout(layout)
        
        # self.defaults_widget.userLineEdit.textChanged.connect(self.validate_inputs)
        self.defaults_widget.initialsLineEdit.textChanged.connect(self.validate_inputs)
        
        if self.exec():
            self.defaults_widget.save_new_defaults()
        
    def validate_inputs(self):
        if self.defaults_widget.initialsLineEdit.hasAcceptableInput(): # & self.defaults_widget.userLineEdit.hasAcceptableInput()
            self.save_button.setEnabled(True)
        else:
            self.save_button.setEnabled(False)

class MakeVialListDialog(QDialog):
    def __init__(self, prefix = None):
        super().__init__()
        
        if prefix:
            prefix = str(prefix)
        
        self.setWindowTitle("ImCapp")
        layout = QVBoxLayout()
        buttons = QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        self.button_box = QDialogButtonBox(buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        self.prefixLineEdit = QLineEdit()
        self.prefixLineEdit.setText(prefix)
        
        self.lowestSpinBox = QSpinBox()
        self.lowestSpinBox.setMinimum(1)
        
        self.highestSpinBox = QSpinBox()
        self.highestSpinBox.setMinimum(1)
        self.highestSpinBox.setMaximum(999)
        self.highestSpinBox.setValue(99)
        
        self.if_save = QCheckBox("Save list as csv")
        
        form_layout = QFormLayout()
        form_layout.addRow(self.tr("Prefix:"), self.prefixLineEdit)
        form_layout.addRow(self.tr("Lowest:"), self.lowestSpinBox)
        form_layout.addRow(self.tr("Highest:"), self.highestSpinBox)
        form_layout.addRow("", self.if_save)
        
        layout.addLayout(form_layout)
        layout.addWidget(self.button_box)
        self.setLayout(layout)
        

# Prepare to run =======================================================
def check_for_camera(camera_number = 0):
    picam2 = None
    try:
        picam2 = Picamera2(camera_number)
    finally:
        return picam2
        
    
# RUN ==================================================================    
def main():
    picam2 = check_for_camera()
    app = QApplication([])
    window = MainWindow(picam2)
    window.show()
    app.exec()

# Run the GUI
if __name__ == '__main__':
    main()
