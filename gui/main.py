import sys
import qdarktheme
from PySide6.QtGui import QFontDatabase

# noinspection PyUnresolvedReferences
from resources import rc_resources  # Loads Qt resources to become available for PySide6
from application import MinSegGUI
from configuration import THEME
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QCoreApplication


if __name__ == "__main__":
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)  # Must be set before the application is created

    app = QApplication(sys.argv)
    QQuickWindow.setGraphicsApi(QSGRendererInterface.OpenGLRhi)
    QFontDatabase.addApplicationFont(":/font/application/assets/JetBrains_Mono/JetBrainsMono-VariableFont_wght.ttf")
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
    window = MinSegGUI()
    window.show()
    sys.exit(app.exec())
