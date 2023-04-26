from functools import wraps
from PySide6.QtCore import Qt, QObject, Property, Signal
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QFrame, QVBoxLayout

REPLACEMENT_TYPES: dict[type, str] = {
    list: 'QVariantList',
    dict: 'QVariantMap'
}


class QMLPropertyMeta(type(QObject)):
    """
    Reduces the definitions necessary to build a working QML backend class.
    The usual approach (https://doc.qt.io/qtforpython-6/PySide6/QtCore/Property.html) is to manually define instances of PySide6.QtCore.Property, getters, setters and associated notifier signals.
    Using this metaclass the signals as well as getters and setters are defined automatically. For this purpose, the QMLProperty must be used as a replacement of PySide6.QtCore.Property.

    \t**Important Note**:\n
    A dynamically created **signal is named according to the QMLProperty** object name **followed by '_changed'**.
    They can be connected to exactly like in the official approach. The only caveat is that attribute/type hints of IDEs will not work, since they are defined dynamically.
    """

    def __new__(cls, name, bases, attrs):
        for key in list(attrs.keys()):
            attr = attrs[key]
            if not isinstance(attr, QMLProperty):
                continue

            replacement_type = REPLACEMENT_TYPES.get(attr.type_, attr.type_)
            notifier = Signal(replacement_type)
            attrs[f'{key}_changed'] = notifier
            attrs[key] = QMLPropertyInstace(type_=attr.type_, name=key, notifier=notifier)

        return super().__new__(cls, name, bases, attrs)


class QMLProperty:
    def __init__(self, type_: type):
        """
        QMLProperty definition. This class is supposed to be instantiated as a class attribute in a class that defines QMLPropertyMeta as its metaclass.
        It is a replacement for the PySide6.QtCore.Property class of PySide6.
        Instances of this class will be replaced with QMLPropertyInstace by the QMLPropertyMeta metaclass.

        \t**Important Note**:\n
        The getters and setters of the property require a reference to a variable that stores the property's actual value.
        Usually, such a variable is instantiated in the property's parent class initializer as its instance attribute.
        However, since QMLProperty objects must be class attributes, those objects and their associated notifier signals are **shared by all instances of the parent class**.
        Consequently, the property value should also be held by the QMLProperty object itself, which is why it is implemented like this in QMLPropertyInstace.
        So keep in mind: Classes that use QMLPropertyMeta metaclass and QMLProperty objects are meant to be singletons!
        There is no need for an external instance attribute that holds the property's value. In fact, it leads to confusion concerning the actual nature of the notifier signals.

        :param type_: The type that is associated with the property.
        """
        self.type_ = type_


class QMLPropertyInstace(Property):
    """
    QMLProperty implementation. Refer to QMLProperty for documentation.
    """

    def __init__(self, type_: type, name: str, notifier: Signal):
        super().__init__(REPLACEMENT_TYPES.get(type_, type_), self._getter, self._setter, notify=notifier)
        self._value = type_()
        self._signal_attr_name = f'{name}_changed'

    def _getter(self, obj: object):
        return self._value

    def _setter(self, obj: object, value: any):
        if not isinstance(self._value, type(value)):  # Raise error if type of _value is not compatible with initially defined type.
            raise TypeError(f"Current value type is {type(self._value)}, but tried to set value of type {type(value)}. The initial type must be respected!")
        signal: Signal = getattr(obj, self._signal_attr_name)

        # Account for mutable objects. Make sure to make them notifying in case of inplace changes.
        set_type = type(value)
        if set_type in {list, dict} and type(self._value) is set_type:
            self._value = make_notifying(self._value, signal)

        if isinstance(value, dict):
            self._value.update(value)
        else:
            self._value = value
            signal.emit(value)


class MakeObjectNotifying:
    """
    Adds notifying signals to lists and dictionaries which are emitted on inplace changes.
    Creates the modified classes just once, on initialization.
    """
    change_methods = {
        list: ['__delitem__', '__iadd__', '__imul__', '__setitem__', 'append',
               'extend', 'insert', 'pop', 'remove', 'reverse', 'sort'],
        dict: ['__delitem__', '__ior__', '__setitem__', 'clear', 'pop',
               'popitem', 'setdefault', 'update']
    }

    def __init__(self):
        if not hasattr(dict, '__ior__'):
            # Dictionaries don't have | operator in Python < 3.9.
            self.change_methods[dict].remove('__ior__')
        self.notified_class = {type_: self.make_notified_class(type_) for type_ in [list, dict]}

    def __call__(self, obj: list | dict, signal: Signal):
        """
        Returns a notifying version of the supplied list or dict.

        :param obj: The list or dict object to be transformed to its notifying version.
        :param signal: The signal to be emitted on any inplace changes of obj.
        :return: The notifying version of obj.
        """
        notified_class = self.notified_class[type(obj)]
        notified_object = notified_class(obj)
        notified_object.signal = signal  # Add the signal to the instance
        return notified_object

    @classmethod
    def make_notified_class(cls, super_class):
        notified_class = type(f'notified_{super_class.__name__}', (super_class,), {})
        for method_name in cls.change_methods[super_class]:
            original_method = getattr(notified_class, method_name)
            notified_method = cls.make_notified_method(original_method, super_class)
            setattr(notified_class, method_name, notified_method)
        return notified_class

    @staticmethod
    def make_notified_method(method, super_class):
        @wraps(method)
        def notified_method(self, *args, **kwargs):
            result = getattr(super_class, method.__name__)(self, *args, **kwargs)
            self.signal.emit(self)
            return result

        return notified_method


make_notifying = MakeObjectNotifying()


class QMLWidgetBackend(QObject, metaclass=QMLPropertyMeta):
    def __init__(self, widget_frame: QFrame, source: str):
        """
        Helper class to initialize quick widget objects from QML file.
        It incorporates the QMLPropertyMeta metaclass that simplifies the interconnection of QML and Python properties.

        \t**Usage**:\n
        Inherit from this class and then specify the properties as class attributes that may be accessed/modified in the QML object and/or in the Python program using QMLProperty.

        \t**Important Note:**\n
        Make sure that the super().__init__() call is made before the QMLProperty objects are accessed, otherwise the programme will crash.
        This is due to the requirement that QObject has to be initialized before any instances or children of PySide6.QtCore.Property are called.

        :param widget_frame: The frame that the referred quick widget centers in.
        :param source: The QML source file path.
        """
        super().__init__()
        self.widget = QQuickWidget(widget_frame)
        self.widget.rootContext().setContextProperty("backend", self)
        self.widget.setSource(source)
        self.widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.widget.setAttribute(Qt.WA_AlwaysStackOnTop)
        self.widget.setAttribute(Qt.WA_TranslucentBackground)
        self.widget.setClearColor(Qt.transparent)
        layout = QVBoxLayout(widget_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.widget)
