
bl_info = {
    "name" : "Import Paint Brushes",
    "author" : "https://github.com/chsh2/import_paint_brush/",
    "description" : "Extract textures from brush files exported by painting software and use them to create Blender brushes",
    "blender" : (3, 3, 0),
    "version" : (0, 2, 0),
    "location" : "File > Import; Brush Settings > Texture > Brush Utilities",
    "warning" : "This addon is still in an early stage of development",
    "doc_url": "",
    "wiki_url": "",
    "tracker_url": "https://github.com/chsh2/import_paint_brush/issues/",
    "category" : "Import-Export"
}

import bpy
from . import auto_load

auto_load.init()

class NODE_MT_paint_brush_tex_utils_submenu(bpy.types.Menu):
    bl_label = "Brush Utilities"
    bl_idname = "NODE_MT_paint_brush_tex_utils_submenu"
    def draw(self, context):
        layout = self.layout
        layout.operator("paint_brush.alpha_soften")
        layout.operator("paint_brush.alpha_clip")
        layout.operator("paint_brush.color_fill")
        layout.operator("paint_brush.invert")

class NODE_MT_paint_brush_mask_utils_submenu(bpy.types.Menu):
    bl_label = "Brush Utilities (Mask)"
    bl_idname = "NODE_MT_paint_brush_mask_utils_submenu"
    def draw(self, context):
        layout = self.layout
        layout.operator("paint_brush.alpha_soften").is_mask = True
        layout.operator("paint_brush.alpha_clip").is_mask = True
        layout.operator("paint_brush.color_fill").is_mask = True
        layout.operator("paint_brush.invert").is_mask = True

def menu_func_tex_utils(self, context):
    layout = self.layout
    layout.menu("NODE_MT_paint_brush_tex_utils_submenu", icon='BRUSHES_ALL', text="Brush Utilities")

def menu_func_mask_utils(self, context):
    layout = self.layout
    layout.menu("NODE_MT_paint_brush_mask_utils_submenu", icon='BRUSHES_ALL', text="Brush Utilities")

def menu_func_import(self, context):
    self.layout.operator('paint_brush.import_brushes', icon='BRUSHES_ALL')

def register():
    auto_load.register()
    bpy.utils.register_class(NODE_MT_paint_brush_tex_utils_submenu)
    bpy.utils.register_class(NODE_MT_paint_brush_mask_utils_submenu)
    bpy.types.IMAGE_PT_tools_brush_texture.append(menu_func_tex_utils)
    bpy.types.IMAGE_PT_tools_mask_texture.append(menu_func_mask_utils)
    bpy.types.VIEW3D_PT_tools_brush_texture.append(menu_func_tex_utils)
    bpy.types.VIEW3D_PT_tools_mask_texture.append(menu_func_mask_utils)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    
def unregister():
    auto_load.unregister()
    bpy.utils.unregister_class(NODE_MT_paint_brush_tex_utils_submenu)
    bpy.utils.unregister_class(NODE_MT_paint_brush_mask_utils_submenu)
    bpy.types.IMAGE_PT_tools_brush_texture.remove(menu_func_tex_utils)
    bpy.types.IMAGE_PT_tools_mask_texture.remove(menu_func_mask_utils)
    bpy.types.VIEW3D_PT_tools_brush_texture.remove(menu_func_tex_utils)
    bpy.types.VIEW3D_PT_tools_mask_texture.remove(menu_func_mask_utils)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)