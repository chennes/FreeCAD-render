# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2019 Yorik van Havre <yorik@uncreated.net>              *
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

"""Cycles renderer for FreeCAD"""

import os
from math import degrees

import FreeCAD as App


def write_camera(pos, rot, updir, target, name):
    """Compute a string in the format of Cycles, that represents a camera"""

    # This is where you create a piece of text in the format of
    # your renderer, that represents the camera.

    # Cam rotation is angle(deg) axisx axisy axisz
    # Scale needs to have z inverted to behave like a decent camera.
    # No idea what they have been doing at blender :)
    snippet = """
    <!-- Generated by FreeCAD - Camera '{n}' -->
    <transform rotate="{a} {r.x} {r.y} {r.z}"
               translate="{p.x} {p.y} {p.z}"
               scale="1 1 -1">
        <camera type="perspective"/>
    </transform>"""

    return snippet.format(n=name, a=degrees(rot.Angle), r=rot.Axis, p=pos)


def write_object(viewobj, mesh, color, alpha):
    """Compute a string in the format of Cycles, that represents a FreeCAD
    object
    """
    # This is where you write your object/view in the format of your
    # renderer. "obj" is the real 3D object handled by this project, not
    # the project itself. This is your only opportunity
    # to write all the data needed by your object (geometry, materials, etc)
    # so make sure you include everything that is needed

    snippet1 = """
    <!-- Generated by FreeCAD - Object '{n}' -->
    <shader name="{n}_mat">
        <diffuse_bsdf name="{n}_bsdf" color="{c[0]}, {c[1]}, {c[2]}"/>"""

    snippet2a = """
        <transparent_bsdf name="{n}_trans" color="1.0, 1.0, 1.0"/>
        <mix_closure name="{n}_mix" fac="{a}"/>
        <connect from="{n}_trans bsdf"  to="{n}_mix closure1"/>
        <connect from="{n}_bsdf bsdf"   to="{n}_mix closure2"/>
        <connect from="{n}_mix closure" to="output surface"/>
    </shader>"""

    snippet2b = """
        <connect from="{n}_bsdf bsdf"   to="output surface"/>
    </shader>"""

    snippet3 = """
    <state shader="{n}_mat">
        <mesh P="{p}"
              nverts="{i}"
              verts="{v}"/>
    </state>\n"""

    snippet = snippet1 + (snippet2a if alpha < 1 else snippet2b) + snippet3

    points = ["{0.x} {0.y} {0.z}".format(p) for p in mesh.Topology[0]]
    verts = ["{} {} {}".format(*v) for v in mesh.Topology[1]]
    nverts = ["3"] * len(verts)

    return snippet.format(n=viewobj.Name,
                          c=color,
                          a=alpha,
                          p="  ".join(points),
                          i="  ".join(nverts),
                          v="  ".join(verts))


def write_pointlight(view, location, color, power):
    """Compute a string in the format of Cycles, that represents a
    PointLight object
    """
    # This is where you write the renderer-specific code
    # to export a point light in the renderer format

    snippet = """
    <!-- Generated by FreeCAD - Pointlight '{n}' -->
    <shader name="{n}_shader">
        <emission name="{n}_emit"
                  color="{c[0]} {c[1]} {c[2]}"
                  strength="{s}"/>
        <connect from="{n}_emit emission"
                 to="output surface"/>
    </shader>
    <state shader="{n}_shader">
        <light type="point"
               co="{p.x} {p.y} {p.z}"
               strength="1 1 1"/>
    </state>\n"""

    return snippet.format(n=view.Name,
                          c=color,
                          p=location,
                          s=power*100)


def write_arealight(name, pos, size_u, size_v, color, power):
    """Compute a string in the format of Cycles, that represents an
    Area Light object
    """
    # Axis
    rot = pos.Rotation
    axis1 = rot.multVec(App.Vector(1, 0.0, 0.0))
    axis2 = rot.multVec(App.Vector(0.0, 1.0, 0.0))
    direction = axis1.cross(axis2)

    snippet = """
    <!-- Generated by FreeCAD - Area light '{n}' -->
    <shader name="{n}_shader">
        <emission name="{n}_emit"
                  color="{c[0]} {c[1]} {c[2]}"
                  strength="{s}"/>
        <connect from="{n}_emit emission"
                 to="output surface"/>
    </shader>
    <state shader="{n}_shader">
        <light type="area"
               co="{p.x} {p.y} {p.z}"
               strength="1 1 1"
               axisu="{u.x} {u.y} {u.z}"
               axisv="{v.x} {v.y} {v.z}"
               sizeu="{a}"
               sizev="{b}"
               size="1"
               dir="{d.x} {d.y} {d.z}" />
    </state>\n"""

    return snippet.format(n=name,
                          c=color,
                          p=pos.Base,
                          s=power*100,
                          u=axis1,
                          v=axis2,
                          a=size_u,
                          b=size_v,
                          d=direction)


def render(project, prefix, external, output, width, height):
    """Run Cycles

    Params:
    - project:  the project to render
    - prefix:   a prefix string for call (will be inserted before path to Lux)
    - external: a boolean indicating whether to call UI (true) or console
                (false) version of Lux
    - width:    rendered image width, in pixels
    - height:   rendered image height, in pixels

    Return: path to output image file
    """

    # Here you trigger a render by firing the renderer
    # executable and passing it the needed arguments, and
    # the file it needs to render

    params = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Render")
    prefix = params.GetString("Prefix", "")
    if prefix:
        prefix += " "
    rpath = params.GetString("CyclesPath", "")
    args = params.GetString("CyclesParameters", "")
    args += " --output " + output
    if not external:
        args += " --background"
    if not rpath:
        App.Console.PrintError("Unable to locate renderer executable. "
                               "Please set the correct path in "
                               "Edit -> Preferences -> Render")
        return ""
    args += " --width " + str(width)
    args += " --height " + str(height)
    cmd = prefix + rpath + " " + args + " " + project.PageResult
    App.Console.PrintMessage(cmd+'\n')
    os.system(cmd)

    return output
