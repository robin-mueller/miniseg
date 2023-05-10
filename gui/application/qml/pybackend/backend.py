from PySide6.QtCore import Qt, QObject, Property, Signal
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QFrame, QVBoxLayout


class NotifiedPropertyMeta(type(QObject)):
    """
    Reduces the definitions necessary to build a working QML backend class.
    The usual approach (https://doc.qt.io/qtforpython-6/PySide6/QtCore/Property.html) is to manually define instances of PySide6.QtCore.Property, getters, setters and associated notifier signals.
    Using this metaclass the signals as well as getters and setters are defined automatically. For this purpose, the NotifiedProperty must be used as a replacement of PySide6.QtCore.Property.

    \t**Important Note**:\n
    This metaclass must only be used in classes that are inheriting from PySide6.QtCore.QObject.
    A dynamically created **signal is named according to the NotifiedProperty** object name **followed by '_changed'**.
    They can be connected to exactly like in the official approach. The only caveat is that attribute/type hints of IDEs will not work, since they are defined dynamically.
    """

    def __new__(cls, name, bases, attrs):
        for key in list(attrs.keys()):
            attr = attrs[key]
            if not isinstance(attr, NotifiedProperty):
                continue

            notifier = Signal(attr.type_)
            attrs[f'{key}_changed'] = notifier
            attrs[key] = NotifiedPropertyInstace(type_=attr.type_, name=key, notifier=notifier)

        return super().__new__(cls, name, bases, attrs)


class NotifiedProperty:
    def __init__(self, type_: type):
        """
        NotifiedProperty definition. This class is supposed to be instantiated as a class attribute in a class that defines NotifiedPropertyMeta as its metaclass.
        It is a replacement for the PySide6.QtCore.Property class of PySide6.
        Instances of this class will be replaced with NotifiedPropertyInstace by the NotifiedPropertyMeta metaclass.

        \t**Important Note**:\n
        The getters and setters of the property require a reference to a variable that stores the property's actual value.
        Usually, such a variable is instantiated in the property's parent class initializer as its instance attribute.
        However, since NotifiedProperty objects must be class attributes, those objects and their associated notifier signals are **shared by all instances of the parent class**.
        Consequently, the property value should also be held by the NotifiedProperty object itself, which is why it is implemented like this in NotifiedPropertyInstace.
        So keep in mind: Classes that use NotifiedPropertyMeta metaclass and NotifiedProperty objects are meant to be singletons!
        There is no need for an external instance attribute that holds the property's value. In fact, it leads to confusion concerning the actual nature of the notifier signals.

        :param type_: The type that is associated with the property.
        """
        self.type_ = type_


class NotifiedPropertyInstace(Property):
    """
    NotifiedProperty implementation. Refer to NotifiedProperty for documentation.
    """

    def __init__(self, type_: type, name: str, notifier: Signal):
        super().__init__(type_, self._getter, self._setter, notify=notifier)
        self._value = type_()
        self._signal_attr_name = f'{name}_changed'

    def _getter(self, obj: object):
        return self._value

    def _setter(self, obj: object, value: any):
        if not isinstance(self._value, type(value)):  # Raise error if type of _value is not compatible with initially defined type.
            raise TypeError(f"Current value type is {type(self._value)}, but tried to set value of type {type(value)}. The initial type must be respected!")
        signal: Signal = getattr(obj, self._signal_attr_name)

        if self._value != value:  # Avoid binding loops
            self._value = value
            signal.emit(value)


class QMLWidgetBackend(QObject, metaclass=NotifiedPropertyMeta):
    def __init__(self, root: QFrame, source: str, size_view_to_root_object=False, **context_properties: any):
        """
        Helper class to initialize quick widget objects from QML file.
        It incorporates the NotifiedPropertyMeta metaclass that simplifies the interconnection of QML and Python properties.

        \t**Usage**:\n
        Inherit from this class and then specify the properties as class attributes that may be accessed/modified in the QML object and/or in the Python program using NotifiedProperty.

        \t**Important Note:**\n
        Make sure that the super().__init__() call is made before the NotifiedProperty objects are accessed, otherwise the programme will crash.
        This is due to the requirement that QObject has to be initialized before any instances or children of PySide6.QtCore.Property are called.

        :param root: The frame that the referred quick widget centers in.
        :param source: The QML source file path.
        :param size_view_to_root_object: If true resize Mode of QQuickWidget is set to QQuickWidget.SizeViewToRootObject else to QQuickWidget.SizeRootObjectToView.
        :param context_properties: Keyword arguments defining the initial properties of the qml object.
        """
        super().__init__()
        self.widget = self.create(root, source, self, size_view_to_root_object, **context_properties)

    @staticmethod
    def create(root: QFrame, source: str, backend: QObject, size_view_to_root_object=False, **context_properties: any):
        widget = QQuickWidget(root)
        widget.rootContext().setContextProperty("backend", backend)
        for name, prop in context_properties.items():
            widget.rootContext().setContextProperty(name, prop)
        widget.setSource(source)
        widget.setResizeMode(QQuickWidget.ResizeMode.SizeViewToRootObject if size_view_to_root_object else QQuickWidget.ResizeMode.SizeRootObjectToView)
        widget.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop)
        widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        widget.setClearColor(Qt.GlobalColor.transparent)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        return widget
