
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QTextEdit, QLabel, QSizePolicy
)
from PyQt5.QtCore import QThread, pyqtSignal

# Import the necessary functions from our generator script
from decoration_generator import get_api_key_from_config, generate_decoration

class GenerationThread(QThread):
    """Worker thread for running the blocking generation task."""
    # Signal to send status updates (string)
    status_updated = pyqtSignal(str)
    # Signal to indicate completion
    finished = pyqtSignal()

    def __init__(self, prompt, api_key):
        super().__init__()
        self.prompt = prompt
        self.api_key = api_key

    def run(self):
        """The entry point for the thread."""
        def status_callback(message):
            # This function will be called by generate_decoration
            self.status_updated.emit(message)

        generate_decoration(self.prompt, self.api_key, status_callback=status_callback)
        self.finished.emit()

class GeneratorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Minecraft Decoration Generator')
        self.init_ui()
        self.api_key = None
        self.generation_thread = None
        self.load_api_key()

    def init_ui(self):
        """Set up the user interface."""
        self.layout = QVBoxLayout(self)

        # --- Input Section ---
        input_layout = QHBoxLayout()
        self.prompt_label = QLabel('Decoration Prompt:')
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText('e.g., a cute fountain or a glowing mushroom')
        input_layout.addWidget(self.prompt_label)
        input_layout.addWidget(self.prompt_input)
        self.layout.addLayout(input_layout)

        # --- Generate Button ---
        self.generate_button = QPushButton('Generate')
        self.generate_button.clicked.connect(self.start_generation)
        self.layout.addWidget(self.generate_button)

        # --- Status/Log Section ---
        self.status_label = QLabel('Status:')
        self.status_box = QTextEdit()
        self.status_box.setReadOnly(True)
        self.status_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.status_label)
        self.layout.addWidget(self.status_box)

        self.resize(500, 400)

    def load_api_key(self):
        """Load the API key on startup."""
        self.api_key = get_api_key_from_config()
        if not self.api_key:
            self.update_status('Error: Could not find a valid DeepSeek API key.\n' 
                               'Please ensure \'deepseek_api_key\' is set in \'config/api_keys.json\' or \n' 
                               'that \'config/api_keys_list.json\' is not empty.')
            self.generate_button.setEnabled(False)
        else:
            self.update_status('API Key loaded successfully. Ready to generate.')

    def start_generation(self):
        """Handle the generate button click."""
        prompt = self.prompt_input.text().strip()
        if not prompt:
            self.update_status('Error: Please enter a prompt for the decoration.')
            return

        self.generate_button.setEnabled(False)
        self.prompt_input.setEnabled(False)
        self.status_box.clear()
        self.update_status(f'Starting generation for: "{prompt}"...')

        # Create and start the worker thread
        self.generation_thread = GenerationThread(prompt, self.api_key)
        self.generation_thread.status_updated.connect(self.update_status)
        self.generation_thread.finished.connect(self.on_generation_finished)
        self.generation_thread.start()

    def update_status(self, message):
        """Append a message to the status box."""
        self.status_box.append(message)

    def on_generation_finished(self):
        """Re-enable UI elements after generation is complete."""
        self.update_status('\nGeneration process finished.')
        self.generate_button.setEnabled(True)
        self.prompt_input.setEnabled(True)

if __name__ == '__main__':
    # Check if PyQt5 is installed
    try:
        from PyQt5 import QtCore
    except ImportError:
        print("Error: PyQt5 is not installed.")
        print("Please install it by running: pip install PyQt5")
        sys.exit(1)

    app = QApplication(sys.argv)
    gui = GeneratorGUI()
    gui.show()
    sys.exit(app.exec_())
