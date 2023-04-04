import sys
import qdarktheme

# noinspection PyUnresolvedReferences
from gui.resources import rc_resources  # Loads Qt resources to become available for PySide6
from gui.include.main_window import MiniSegGUI
from configuration import THEME
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QCoreApplication


if __name__ == "__main__":
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    QQuickWindow.setGraphicsApi(QSGRendererInterface.OpenGLRhi)
    
    app = QApplication(sys.argv)
    qdarktheme.setup_theme(
        custom_colors={
            "[dark]": {
                "foreground": THEME.foreground,
                "background": THEME.background,
                "border": THEME.border,
                "primary": THEME.primary
            }
        },
        corner_shape="sharp"
    )
    window = MiniSegGUI()
    window.show()
    sys.exit(app.exec())
