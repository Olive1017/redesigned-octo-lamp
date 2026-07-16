"""启动程序"""

import sys
import logging
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from gui.log_handler import QtLogHandler


def main():
    """启动 GUI"""
    # Attach Qt log handler so all logging goes to the UI log panel (thread-safe)
    qt_handler = QtLogHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    qt_handler.setFormatter(formatter)
    logging.getLogger().addHandler(qt_handler)
    # Ensure INFO and above are handled so info-level logs reach the UI
    logging.getLogger().setLevel(logging.INFO)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
