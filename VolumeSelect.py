bl_info = {
    "name": "Volume Select",
    "author": "ChatGPT",
    "version": (1, 2),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Volume Select",
    "description": "Select loose mesh components by bounding-box volume using multiple, draggable threshold ranges.",
    "category": "Mesh",
}

import bpy
import bmesh
from mathutils import Vector

# ------------------------------------------------------------
# Data container for a single threshold range
# ------------------------------------------------------------
class LS_ThresholdItem(bpy.types.PropertyGroup):
    """Holds one range with optional min/max values"""

    use_min: bpy.props.BoolProperty(
        name="Use Min",
        description="Enable minimum bound for this range",
        default=False,
    )
    min_value: bpy.props.FloatProperty(
        name="Min",
        description="Minimum bounding-box volume for this range (scene units^3)",
        default=0.0,
        precision=6,
        soft_min=0.0,
        soft_max=1e6,
        step=1,
    )

    use_max: bpy.props.BoolProperty(
        name="Use Max",
        description="Enable maximum bound for this range",
        default=False,
    )
    max_value: bpy.props.FloatProperty(
        name="Max",
        description="Maximum bounding-box volume for this range (scene units^3)",
        default=0.1,
        precision=6,
        soft_min=0.0,
        soft_max=1e6,
        step=1,
    )

    label: bpy.props.StringProperty(name="Label", default="Range")

# ------------------------------------------------------------
# UIList: no numbering, just label + min/max
# ------------------------------------------------------------
class LS_UL_thresholds(bpy.types.UIList):
    """Custom UIList row drawing without numbering"""
        
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.label)
        
        if item.use_min:
            row.prop(item, "min_value", text="Min")
        else:
            row.label(text="Min: -")
        
        if item.use_max:
            row.prop(item, "max_value", text="Max")
        else:
            row.label(text="Max: +")

# ------------------------------------------------------------
# Operators to add/remove/move ranges
# ------------------------------------------------------------
class LS_OT_add_range(bpy.types.Operator):
    bl_idname = "ls.add_range"
    bl_label = "Add Range"
    bl_description = "Add a new threshold range"

    def execute(self, context):
        scn = context.scene
        item = scn.ls_ranges.add()
        item.label = f"Range {len(scn.ls_ranges)}"
        scn.ls_ranges_index = len(scn.ls_ranges) - 1
        return {'FINISHED'}

class LS_OT_remove_range(bpy.types.Operator):
    bl_idname = "ls.remove_range"
    bl_label = "Remove Range"
    bl_description = "Remove the active threshold range"

    @classmethod
    def poll(cls, context):
        return context.scene.ls_ranges and context.scene.ls_ranges_index >= 0

    def execute(self, context):
        scn = context.scene
        idx = scn.ls_ranges_index
        scn.ls_ranges.remove(idx)
        scn.ls_ranges_index = min(max(0, idx-1), len(scn.ls_ranges)-1)
        return {'FINISHED'}

class LS_OT_move_range(bpy.types.Operator):
    bl_idname = "ls.move_range"
    bl_label = "Move Range"
    direction: bpy.props.EnumProperty(items=(('UP','Up',''),('DOWN','Down','')))

    @classmethod
    def poll(cls, context):
        scn = context.scene
        return scn.ls_ranges and scn.ls_ranges_index >= 0

    def execute(self, context):
        scn = context.scene
        idx = scn.ls_ranges_index
        if self.direction == 'UP' and idx > 0:
            scn.ls_ranges.move(idx, idx-1)
            scn.ls_ranges_index = idx-1
        elif self.direction == 'DOWN' and idx < len(scn.ls_ranges)-1:
            scn.ls_ranges.move(idx, idx+1)
            scn.ls_ranges_index = idx+1
        return {'FINISHED'}

# ------------------------------------------------------------
# Tutorial popup operator
# ------------------------------------------------------------
class LS_OT_show_tutorial(bpy.types.Operator):
    bl_idname = "ls.show_tutorial"
    bl_label = "Show Tutorial"
    bl_description = "Open a short tutorial explaining how to use the panel"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=600)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Volume Select — Quick Tutorial")
        layout.separator()
        layout.label(text="1) Select a mesh object and enter Edit Mode (Tab).")
        layout.label(text="2) Choose the element type in the top of the sidebar: Vert/Edge/Face.")
        layout.label(text="3) Create ranges with 'Add Range'. Use toggles to enable Min/Max.")
        layout.label(text="   - If Min is disabled, the range starts from 0.")
        layout.label(text="   - If Max is disabled, the range is open-ended upward.")
        layout.label(text="4) Reorder ranges by selecting them and pressing the up/down arrows or drag.")
        layout.label(text="5) Press 'Select by Threshold Ranges' to apply selection.")
        layout.separator()
        layout.label(text="Notes:")
        layout.label(text="- Volumes are bounding-box volumes in scene units^3 (world-space).")
        layout.label(text="- Use large Max values for big scenes (sliders allow large numbers).")

    def execute(self, context):
        return {'FINISHED'}

# ------------------------------------------------------------
# Main operator: perform selection
# ------------------------------------------------------------
class LS_OT_select_by_ranges(bpy.types.Operator):
    bl_idname = "ls.select_by_ranges"
    bl_label = "Select by Threshold Ranges"
    bl_description = "Select loose components whose bounding-box volume falls into any user-defined range"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == 'MESH' and context.mode.startswith('EDIT')

    def execute(self, context):
        scn = context.scene
        obj = context.object
        mesh = obj.data

        # Build list of ranges
        ranges = []
        for item in scn.ls_ranges:
            vmin = item.min_value if item.use_min else None
            vmax = item.max_value if item.use_max else None
            ranges.append((vmin, vmax))

        # Operate in bmesh
        bm = bmesh.from_edit_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # Selection mode from toolbar
        use_verts, use_edges, use_faces = context.tool_settings.mesh_select_mode

        # Find connected components
        unvisited = set(bm.verts)
        parts = []
        while unvisited:
            seed = unvisited.pop()
            stack = [seed]
            comp = {seed}
            while stack:
                v = stack.pop()
                for e in v.link_edges:
                    u = e.other_vert(v)
                    if u in unvisited:
                        unvisited.remove(u)
                        comp.add(u)
                        stack.append(u)
            parts.append(comp)

        # Compute world-space bounding-box volumes
        volumes = []
        for comp in parts:
            world_coords = [obj.matrix_world @ v.co for v in comp]
            min_c = Vector((min(c.x for c in world_coords),
                            min(c.y for c in world_coords),
                            min(c.z for c in world_coords)))
            max_c = Vector((max(c.x for c in world_coords),
                            max(c.y for c in world_coords),
                            max(c.z for c in world_coords)))
            size = max_c - min_c
            volumes.append(abs(size.x * size.y * size.z))

        # Clear selection
        if use_verts:
            for v in bm.verts: v.select = False
        if use_edges:
            for e in bm.edges: e.select = False
        if use_faces:
            for f in bm.faces: f.select = False

        # Select components matching ranges
        for comp, vol in zip(parts, volumes):
            matched = False
            for vmin, vmax in ranges:
                if vmin is not None and vol < vmin:
                    continue
                if vmax is not None and vol > vmax:
                    continue
                matched = True
                break
            if not matched:
                continue

            if use_verts:
                for v in comp: v.select = True
            if use_edges:
                for v in comp:
                    for e in v.link_edges:
                        if e.verts[0] in comp and e.verts[1] in comp:
                            e.select = True
            if use_faces:
                for f in bm.faces:
                    if all(v in comp for v in f.verts):
                        f.select = True

        bmesh.update_edit_mesh(mesh)
        return {'FINISHED'}

# ------------------------------------------------------------
# Panel UI
# ------------------------------------------------------------
class LS_PT_panel(bpy.types.Panel):
    bl_label = "Volume Select"
    bl_idname = "LS_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Volume Select'

    def draw(self, context):
        layout = self.layout
        scn = context.scene

        row = layout.row()
        row.template_list(
            "LS_UL_thresholds",
            "ls_thresholds_list",
            scn,
            "ls_ranges",
            scn,
            "ls_ranges_index",
            rows=4,
        )

        col = row.column(align=True)
        col.operator('ls.add_range', icon='ADD', text='')
        col.operator('ls.remove_range', icon='REMOVE', text='')
        col.separator()
        col.operator('ls.move_range', icon='TRIA_UP', text='').direction = 'UP'
        col.operator('ls.move_range', icon='TRIA_DOWN', text='').direction = 'DOWN'

        # Detailed settings for the active range
        idx = scn.ls_ranges_index
        if idx >= 0 and idx < len(scn.ls_ranges):
            item = scn.ls_ranges[idx]
            box = layout.box()
            box.prop(item, 'label')
            row = box.row(align=True)
            row.prop(item, 'use_min', toggle=True)
            if item.use_min:
                row.prop(item, 'min_value', text='')
            row = box.row(align=True)
            row.prop(item, 'use_max', toggle=True)
            if item.use_max:
                row.prop(item, 'max_value', text='')

        # Bottom buttons: Tutorial and Apply
        layout.separator()
        row = layout.row()
        row.operator('ls.show_tutorial', icon='HELP')
        row.operator('ls.select_by_ranges', icon='VIEWZOOM')

# ------------------------------------------------------------
# Registration
# ------------------------------------------------------------
classes = [
    LS_ThresholdItem,
    LS_UL_thresholds,
    LS_OT_add_range,
    LS_OT_remove_range,
    LS_OT_move_range,
    LS_OT_show_tutorial,
    LS_OT_select_by_ranges,
    LS_PT_panel,
]

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.ls_ranges = bpy.props.CollectionProperty(type=LS_ThresholdItem)
    bpy.types.Scene.ls_ranges_index = bpy.props.IntProperty(default=-1)
    bpy.context.scene.ls_ranges.clear()
    bpy.context.scene.ls_ranges_index = -1

def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.ls_ranges
    del bpy.types.Scene.ls_ranges_index

if __name__ == "__main__":
    register()
