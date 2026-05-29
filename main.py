import os
import subprocess
import sys
import threading
from pathlib import Path

import speech_recognition as sr

VENV_DIR = Path(__file__).resolve().parent / ".venv"
PYTHON_VERSION = f"python{sys.version_info.major}.{sys.version_info.minor}"

if os.name == "nt":
    QT_ROOT = VENV_DIR / "Lib" / "site-packages" / "PySide6" / "Qt"
    os.environ.setdefault("QT_PLUGIN_PATH", str(QT_ROOT / "plugins"))
    os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(QT_ROOT / "plugins" / "platforms"))
    os.add_dll_directory(str(QT_ROOT / "bin"))
    os.add_dll_directory(str(QT_ROOT / "plugins" / "platforms"))
else:
    QT_ROOT = VENV_DIR / "lib" / PYTHON_VERSION / "site-packages" / "PySide6" / "Qt"
    os.environ.setdefault("QT_PLUGIN_PATH", str(QT_ROOT / "plugins"))
    os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(QT_ROOT / "plugins" / "platforms"))
    os.environ.setdefault("DYLD_FRAMEWORK_PATH", str(QT_ROOT / "lib"))
    os.environ.setdefault("DYLD_LIBRARY_PATH", str(QT_ROOT / "lib"))

from PySide6.QtCore import Q_ARG, QMetaObject, Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)


class EchoTalkWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EchoTalk - Sordo escribe / oyente habla")
        self.resize(1000, 700)

        self.is_recording = False
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.capture_thread = None
        self.stop_event = threading.Event()

        self._build_ui()
        self._apply_theme()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(18)

        title = QLabel("EchoTalk")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: #F5F7FA;")
        main_layout.addWidget(title)

        subtitle = QLabel("El sordo escribe y la otra persona puede escuchar lo que dice.")
        subtitle.setStyleSheet("font-size: 14px; color: #D7E0EA;")
        main_layout.addWidget(subtitle)

        self.status_label = QLabel("Estado: OFF")
        self.status_label.setStyleSheet("font-size: 16px; color: #FFD166; font-weight: 600;")
        main_layout.addWidget(self.status_label)

        self.transcription_display = QTextEdit()
        self.transcription_display.setReadOnly(True)
        self.transcription_display.setPlaceholderText("Aquí aparecerá lo que diga la otra persona para el sordo.")
        self.transcription_display.setStyleSheet(
            "background-color: #121826; color: #F3F7FF; border: 1px solid #2C3E60; "
            "border-radius: 14px; padding: 14px; font-size: 18px;"
        )
        main_layout.addWidget(self.transcription_display, stretch=2)

        self.history_display = QTextEdit()
        self.history_display.setReadOnly(True)
        self.history_display.setPlaceholderText("Historial de conversación")
        self.history_display.setStyleSheet(
            "background-color: #182234; color: #ECF2FF; border: 1px solid #324766; "
            "border-radius: 12px; padding: 10px; font-size: 13px;"
        )
        main_layout.addWidget(self.history_display, stretch=1)

        text_row = QHBoxLayout()
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Escribe aquí lo que quiere decir el sordo")
        self.text_input.setStyleSheet(
            "background-color: #121826; color: #F3F7FF; border: 1px solid #2C3E60; "
            "border-radius: 10px; padding: 10px; font-size: 14px;"
        )
        text_row.addWidget(self.text_input, stretch=1)

        self.send_button = QPushButton("Enviar al oyente")
        self.send_button.setStyleSheet(
            "QPushButton { background-color: #2E8B57; color: #FFFFFF; border-radius: 10px; "
            "padding: 10px 14px; font-size: 14px; font-weight: 700; } "
            "QPushButton:hover { background-color: #3AA96B; } "
            "QPushButton:pressed { background-color: #247A46; }"
        )
        self.send_button.clicked.connect(self._send_manual_text)
        text_row.addWidget(self.send_button)
        main_layout.addLayout(text_row)

        self.record_button = QPushButton("Iniciar grabación")
        self.record_button.setStyleSheet(
            "QPushButton { background-color: #1F6FEB; color: #FFFFFF; border-radius: 14px; "
            "padding: 14px; font-size: 16px; font-weight: 700; } "
            "QPushButton:hover { background-color: #2A80FF; } "
            "QPushButton:pressed { background-color: #1758C4; }"
        )
        self.record_button.clicked.connect(self.toggle_recording)
        main_layout.addWidget(self.record_button)

        self.simulation_timer = None

    def _apply_theme(self):
        self.setStyleSheet(
            "QWidget { background-color: #0B1220; color: #F5F7FA; font-family: Arial, sans-serif; } "
            "QLabel { color: #F5F7FA; } "
            "QTextEdit { color: #F5F7FA; }"
        )

    def toggle_recording(self):
        if not self.is_recording:
            self._start_listening()
        else:
            self._stop_listening()

    def _start_listening(self):
        self.is_recording = True
        self.stop_event.clear()
        self.transcription_display.clear()
        self.transcription_display.append("🎙 Escuchando...")
        self.status_label.setText("Estado: LISTENING")
        self.record_button.setText("Detener grabación")
        self.record_button.setStyleSheet(
            "QPushButton { background-color: #C0392B; color: #FFFFFF; border-radius: 14px; "
            "padding: 14px; font-size: 16px; font-weight: 700; } "
            "QPushButton:hover { background-color: #E74C3C; } "
            "QPushButton:pressed { background-color: #A93226; }"
        )
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        print("[EchoTalk] Micrófono: captura iniciada")

    def _stop_listening(self):
        self.stop_event.set()
        self.is_recording = False
        self.status_label.setText("Estado: PROCESSING")
        self.record_button.setText("Iniciar grabación")
        self.record_button.setStyleSheet(
            "QPushButton { background-color: #1F6FEB; color: #FFFFFF; border-radius: 14px; "
            "padding: 14px; font-size: 16px; font-weight: 700; } "
            "QPushButton:hover { background-color: #2A80FF; } "
            "QPushButton:pressed { background-color: #1758C4; }"
        )
        if self.capture_thread and self.capture_thread.is_alive() and threading.current_thread() is not self.capture_thread:
            self.capture_thread.join(timeout=2)
        self.status_label.setText("Estado: OFF")
        print("[EchoTalk] Micrófono: captura detenida")

    def _capture_loop(self):
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                while not self.stop_event.is_set():
                    try:
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                        QMetaObject.invokeMethod(self, "_set_status", Qt.QueuedConnection, Q_ARG(str, "PROCESSING"))
                        text = self.recognizer.recognize_google(audio, language="es-ES")
                        QMetaObject.invokeMethod(self, "_append_transcript", Qt.QueuedConnection, Q_ARG(str, text))
                        QMetaObject.invokeMethod(self, "_append_history", Qt.QueuedConnection,
                                                 Q_ARG(str, text), Q_ARG(str, "Oyente"))
                    except sr.WaitTimeoutError:
                        continue
                    except sr.UnknownValueError:
                        QMetaObject.invokeMethod(self, "_show_error", Qt.QueuedConnection,
                                                 Q_ARG(str, "No se entendió el audio. Intente de nuevo."))
                    except sr.RequestError:
                        QMetaObject.invokeMethod(self, "_show_error", Qt.QueuedConnection,
                                                 Q_ARG(str, "No se pudo conectar al servicio de reconocimiento."))
        except OSError as exc:
            QMetaObject.invokeMethod(self, "_show_error", Qt.QueuedConnection,
                                     Q_ARG(str, f"No se pudo acceder al micrófono: {exc}"))
        finally:
            QMetaObject.invokeMethod(self, "_reset_button_state", Qt.QueuedConnection)

    @Slot(str)
    def _append_transcript(self, text):
        if not text:
            return
        self.transcription_display.setPlainText(text)

    @Slot(str, str)
    def _append_history(self, text, speaker="Sordo"):
        if text:
            self.history_display.append(f"[{speaker}] {text}")

    def _send_manual_text(self):
        text = self.text_input.text().strip()
        if not text:
            self.transcription_display.setPlainText("Escribe algo antes de enviar.")
            return
        self._append_history(text, "Sordo")
        self.transcription_display.setPlainText(text)
        self._speak_text(text)
        self.text_input.clear()
        self.status_label.setText("Estado: OFF")

    def _speak_text(self, text):
        try:
            if sys.platform == "darwin":
                subprocess.run(["say", text], check=False, capture_output=True, text=True)
                print("[EchoTalk] Texto leído en voz alta para la otra persona.")
                return
            try:
                import pyttsx3

                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except Exception:
                print("[EchoTalk] No se pudo reproducir voz automática en esta plataforma.")
        except Exception as exc:
            print(f"[EchoTalk] Error al reproducir voz: {exc}")

    @Slot(str)
    def _show_error(self, message):
        self.transcription_display.setPlainText(message)
        self._reset_button_state()
        self.status_label.setText("Estado: OFF")
        self.is_recording = False
        print(f"[EchoTalk] Error: {message}")

    @Slot()
    def _reset_button_state(self):
        self.record_button.setText("Iniciar grabación")
        self.record_button.setStyleSheet(
            "QPushButton { background-color: #1F6FEB; color: #FFFFFF; border-radius: 14px; "
            "padding: 14px; font-size: 16px; font-weight: 700; } "
            "QPushButton:hover { background-color: #2A80FF; } "
            "QPushButton:pressed { background-color: #1758C4; }"
        )

    @Slot(str)
    def _set_status(self, status):
        self.status_label.setText(f"Estado: {status}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EchoTalkWindow()
    window.show()
    sys.exit(app.exec())
