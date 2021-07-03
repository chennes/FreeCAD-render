# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2021 Howetuft <howetuft@gmail.com>                      *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

"""This module implements base classes for Render workbench."""

from collections import namedtuple
import functools
import itertools
import sys
import os

from pivy import coin
import FreeCAD as App
import FreeCADGui as Gui
from PySide.QtGui import QAction, QIcon
from PySide.QtCore import QObject, SIGNAL, QT_TRANSLATE_NOOP

from Render.utils import translate
from Render.constants import ICONDIR

# ===========================================================================
#                                 Helpers
# ===========================================================================


def get_cumulative_dict_attribute(obj, attr_name):
    """Get a merged attribute from dictionary attributes in a class hierarchy.

    Args:
    obj -- obj from which to determine class hierarchy
    attr_name -- attribute name
    """
    attributes = [
        getattr(cls, attr_name)
        for cls in reversed(obj.__class__.__mro__)
        if attr_name in vars(cls)
    ]
    res = {}
    for attribute in attributes:
        res.update(attribute)
    return res


Prop = namedtuple(
    "Prop", ["Type", "Group", "Doc", "Default", "EditorMode"], defaults=[0]
)

CtxMenuItem = namedtuple(
    "CtxMenuItem", ["name", "action", "icon"], defaults=[None]
)


# ===========================================================================
#                                 Interfaces
# ===========================================================================


class InterfaceBaseFeature:
    # TODO Interface should subclass ABC
    """An interface to base class for FreeCAD scripted objects (BaseFeature).

    This class lists methods and properties that can/should be overriden by
    subclasses.
    """

    # These constants must be overriden when subclassing (mandatory)
    VIEWPROVIDER = ""  # The name of the associated ViewProvider class (str)
    PROPERTIES = {}  # The properties of the object (dict of Prop)

    # These constants can be overriden when subclassing (optional)
    NAMESPACE = "Render"  # The namespace where feature and viewprovider are
    TYPE = ""  # The type of the object (str). If empty, default to class name

    def on_set_properties_cb(self, fpo):
        """Complete the operation of internal _set_properties (callback).

        This method is a hook for sub-class to complete properties setting,
        in addition to canonic _set_properties mechanism.
        """

    def on_create_cb(self, fpo, viewp, **kwargs):
        """Complete the operation of 'create' (callback).

        This method is a hook for subclass to complete object creation,
        in addition to canonic 'create' mechanism. Subclass can override if
        needed.

        Params:
            fpo -- Related FeaturePython object
            viewp -- Related ViewProvider object
            kwargs -- Keyword arguments
        """

    @classmethod
    def pre_create_cb(cls, **kwargs):
        """Precede the operation of 'create' (callback).

        This method is a hook for subclass to precede object creation,
        in addition to canonic 'create' mechanism. Subclass can override if
        needed.

        Params:
            kwargs -- Keyword arguments
        """


class InterfaceBaseViewProvider:
    # TODO Interface should subclass ABC
    """An interface to base class for FreeCAD ViewProvider.

    This class lists methods and properties that can/should be overriden by
    subclasses.
    """
    # TODO Reformat comments for properties
    ICON = ""  # Icon name. By default, looks into ICONDIR.
    # If name starts with ":", will look into FreeCAD icons

    DISPLAY_MODES = ["Default"]  # Display modes
    # First item provides the default mode, so
    # please keep at least one item there

    ALWAYS_VISIBLE = False  # If True, make the object always visible in tree

    ON_CHANGED = {}  # A dictionary Property: Method (strings).
    # Handles changes in ViewProviderDocumentObject data,
    # see onChanged

    ON_UPDATE = {}  # A dictionary Property: Method (strings)
    # Handles changes in ViewProviderDocument data,
    # see onUpdateData

    CONTEXT_MENU = []  # An list of CtxMenuItem, for the contextual menu

    def on_attach_cb(self, vobj):
        """Complete 'attach' method (callback).

        Subclasses can override this method.
        """


# ===========================================================================
#                                 Implementations
# ===========================================================================


class BaseFeature(InterfaceBaseFeature):
    """A base class for FreeCAD Feature.

    This base is to be used for workbench scripted objects.
    It provides the following features:
    - Properties management (automatically create/update properties list
      from PROPERTIES class constant)
    - Access to the FeaturePython related object, via 'fpo' property
    - Factory method 'create' to generate new instances, along with view
      providers
    """

    # Internal variables, do not modify
    _fpos = dict()

    def __init__(self, fpo):
        """Initialize object.

        Params:
            fpo -- Related FeaturePython object
        """
        self._set_properties(fpo)

    def onDocumentRestored(self, fpo):
        """Respond to document restoration event (callback).

        Params:
            fpo -- Related FeaturePython object
        """
        self._set_properties(fpo)

    def _set_properties(self, fpo):
        """Set underlying FeaturePython object's properties."""
        self.fpo = fpo
        self.__module__ = self.NAMESPACE
        fpo.Proxy = self

        properties = get_cumulative_dict_attribute(self, "PROPERTIES")
        for name in properties.keys() - set(fpo.PropertiesList):
            spec = Prop._make(self.PROPERTIES[name])
            prop = fpo.addProperty(spec.Type, name, spec.Group, spec.Doc, 0)
            setattr(prop, name, spec.Default)
            fpo.setEditorMode(name, spec.EditorMode)
        self.on_set_properties_cb(fpo)

    @property
    def fpo(self):
        """Get underlying FeaturePython object."""
        return self._fpos[id(self)]

    @fpo.setter
    def fpo(self, new_fpo):
        """Set underlying FeaturePython object."""
        self._fpos[id(self)] = new_fpo

    @property
    def type(self):
        """Get 'type' property."""
        return self.TYPE if self.TYPE else self.__class__.__name__

    @property
    def Type(self):  # pylint: disable=invalid-name
        """Get 'Type' property."""
        return self.TYPE if self.TYPE else self.__class__.__name__

    @classmethod
    def create(cls, document=None, **kwargs):
        """Create an instance of object in a document.

        Factory method to create a new instance of this object.
        The instance is created into the active document (default).
        Optionally, it is possible to specify a target document, in which case
        the object is created in the given document.

        This method also create the FeaturePython and the ViewProvider related
        objects. Please note that the ViewProvider class must exists in module
        namespace.

        Args:
            document -- The document where to create the instance (optional,
              default is ActiveDocument).

        Returns:
            The newly created Object, the FeaturePython and the
            ViewProvider objects.
        """
        cls.pre_create_cb(**kwargs)
        doc = document if document else App.ActiveDocument
        assert doc, (
            "Cannot create object if no document is provided "
            "and no document is active"
        )
        _type = cls.TYPE if cls.TYPE else cls.__name__
        fpo = doc.addObject("App::FeaturePython", _type)
        obj = cls(fpo)
        try:
            viewp_class = getattr(sys.modules[cls.NAMESPACE], cls.VIEWPROVIDER)
        except AttributeError as original_exc:
            msg = "Bad {d}.VIEWPROVIDER value in '{d}' creation: '{v}'\n"
            msg = msg.format(d=cls.__name__, v=cls.VIEWPROVIDER)
            trace = sys.exc_info()[2]
            raise ValueError(msg).with_traceback(trace) from original_exc
        viewp = viewp_class(fpo.ViewObject)
        obj.on_create_cb(fpo, viewp, **kwargs)
        App.ActiveDocument.recompute()
        return obj, fpo, viewp


class BaseViewProvider(InterfaceBaseViewProvider):
    """A base class for FreeCAD ViewProvider.

    This base is to be used for workbench scripted objects' ViewProviders.
    """

    def __init__(self, vobj):
        """Initialize View Provider.

        Args:
            vobj -- Related ViewProviderDocumentObject
        """
        vobj.Proxy = self
        self.fpo = vobj.Object  # Related FeaturePython object
        self.__module__ = "Render"
        App.Console.PrintMessage("BaseViewProvider.__init__")

    def attach(self, vobj):
        """Respond to created/restored object event (callback).

        Args:
            vobj -- Related ViewProviderDocumentObject
        """
        self.fpo = vobj.Object  # Related FeaturePython object
        self.__module__ = "Render"
        self.on_attach_cb(vobj)

    @functools.lru_cache(maxsize=128)
    def _context_menu_mapping(self):
        """Get context menu items."""
        res = itertools.chain.from_iterable(
            [
                cls.CONTEXT_MENU
                for cls in reversed(self.__class__.__mro__)
                if "CONTEXT_MENU" in vars(cls)
            ]
        )
        return list(res)

    def setupContextMenu(self, vobj, menu):
        """Set up the object's context menu in GUI (callback)."""
        for item in self._context_menu_mapping():
            if item.icon:
                icon = QIcon(os.path.join(ICONDIR, item.icon))
                action = QAction(icon, item.name, menu)
            else:
                action = QAction(item.name, menu)
            method = getattr(self, item.action)
            QObject.connect(action, SIGNAL("triggered()"), method)
            menu.addAction(action)

    def isShow(self):
        """Define the visibility of the object in the tree view (callback)."""
        return True if self.ALWAYS_VISIBLE else self.fpo.Visibility

    def claimChildren(self):
        """Deliver the children belonging to this object (callback)."""
        try:
            return self.fpo.Group
        except AttributeError:
            return []

    def getIcon(self):
        """Return the icon which will appear in the tree view (callback)."""
        icon = (
            self.ICON
            if self.ICON.startswith(":")
            else os.path.join(ICONDIR, self.ICON)
        )
        return icon

    @functools.lru_cache(maxsize=128)
    def _on_changed_mapping(self):
        """Get 'on change' mapping."""
        return get_cumulative_dict_attribute(self, "ON_CHANGED")

    def onChanged(self, vpdo, prop):
        """Respond to property changed event (callback).

        This code is executed when a property of the FeaturePython object is
        changed.

        Args:
            vpdo -- related ViewProviderDocumentObject (where properties are
                stored)
            prop -- property name (as a string)
        """
        try:
            on_changed = self._on_changed_mapping()
            method = getattr(self, on_changed[prop])
        except KeyError:
            pass  # Silently ignore when switcher provides no action
        else:
            method(vpdo)

    @functools.lru_cache(maxsize=128)
    def _on_update_mapping(self):
        """Get 'on update data' mapping."""
        return get_cumulative_dict_attribute(self, "ON_UPDATE")

    def updateData(self, fpo, prop):
        """Respond to FeaturePython's property changed event (callback).

        This code is executed when a property of the underlying FeaturePython
        object is changed.

        Args:
            fpo -- related FeaturePython object
            prop -- property name
        """
        on_update = self._on_update_mapping()
        try:
            method = getattr(self, on_update[prop])
        except KeyError:
            pass  # Silently ignore when switcher provides no action
        else:
            method(fpo)

    def __getstate__(self):
        """Provide data representation for object."""
        return None

    def __setstate__(self, state):
        """Restore object state from data representation."""
        return None

    def getDisplayModes(self, vobj):
        """Return a list of display modes (callback)."""
        return self.DISPLAY_MODES

    def getDefaultDisplayMode(self):
        """Return the name of the default display mode (callback).

        The display mode must be defined in getDisplayModes.
        """
        return self.DISPLAY_MODES[0]

    def setDisplayMode(self, mode):  # pylint: disable=no-self-use
        """Set the display mode (callback).

        Map the display mode defined in attach with those defined in
        getDisplayModes. Since they have the same names nothing needs to be
        done.
        """
        return mode


# ===========================================================================
#                                 Mixins
# ===========================================================================


class PointableFeatureMixin:
    """Mixin for Pointable feature.

    This mixin allows a feature to be "pointable", ie to support
    'point_at' action.
    """
    PROPERTIES = {
        "Placement": Prop(
            "App::PropertyPlacement",
            "Pointable",
            QT_TRANSLATE_NOOP("Render", "Object placement"),
            App.Placement(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 0),
        ),
    }

    def point_at(self, point):
        """Make camera point at a given target point.

        Args:
            point -- Geometrical point to point at (having x, y, z properties).
        """
        fpo = self.fpo
        current_target = fpo.Placement.Rotation.multVec(App.Vector(0, 0, -1))
        base = fpo.Placement.Base
        new_target = App.Vector(
            point.x - base.x, point.y - base.y, point.z - base.z
        )
        axis = current_target.cross(new_target)
        if not axis.Length:
            # Don't try to rotate if axis is a null vector...
            return
        angle = degrees(new_target.getAngle(current_target))
        rotation = App.Rotation(axis, angle)
        fpo.Placement.Rotation = rotation.multiply(fpo.Placement.Rotation)


class PointableViewProviderMixin:
    # TODO Mixin for feature
    """Mixin for Pointable ViewProviders.

    This mixin allows a ViewProvider to be "pointable", ie to support
    'point_at' actions.
    """
    CONTEXT_MENU = [
        CtxMenuItem(
            QT_TRANSLATE_NOOP("Render", "Point at..."),
            "point_at",
        ),
    ]

    def __init__(self, vobj):
        """Initialize Mixin."""
        super().__init__(vobj)
        self.callback = None  # For point_at method

    def point_at(self):
        """Make this object point at another object.

        User will be requested to select an object to point at.
        """
        msg = (
            translate(
                "Render", "[Point at] Please select target (on geometry)"
            )
            + "\n"
        )
        App.Console.PrintMessage(msg)
        self.callback = Gui.ActiveDocument.ActiveView.addEventCallbackPivy(
            coin.SoMouseButtonEvent.getClassTypeId(), self._point_at_cb
        )

    def _point_at_cb(self, event_cb):
        """`point_at` callback.

        Args:
            event_cb -- coin event callback object
        """
        event = event_cb.getEvent()
        if (
            event.getState() == coin.SoMouseButtonEvent.DOWN
            and event.getButton() == coin.SoMouseButtonEvent.BUTTON1
        ):
            # Get point
            picked_point = event_cb.getPickedPoint()
            try:
                point = App.Vector(picked_point.getPoint())
            except AttributeError:
                # No picked point (outside geometry)
                msg = (
                    translate(
                        "Render",
                        "[Point at] Target outside geometry " "-- Aborting",
                    )
                    + "\n"
                )
                App.Console.PrintMessage(msg)
            else:
                # Make underlying object point at target point
                self.fpo.Proxy.point_at(point)
                msg = (
                    translate(
                        "Render",
                        "[Point at] Now pointing at " "({0.x}, {0.y}, {0.z})",
                    )
                    + "\n"
                )
                App.Console.PrintMessage(msg.format(point))
            finally:
                # Remove coin event catcher
                Gui.ActiveDocument.ActiveView.removeEventCallbackPivy(
                    coin.SoMouseButtonEvent.getClassTypeId(), self.callback
                )
