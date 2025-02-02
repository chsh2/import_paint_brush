import bpy
import numpy as np
from mathutils import kdtree
import colorsys

def smoothstep(x):
    if x<0:
        return 0
    if x>1:
        return 1
    return 3*(x**2) - 2*(x**3)

def load_img_pixels(img_data: bpy.types.Image):
    return np.array(img_data.pixels).reshape(img_data.size[1], img_data.size[0], img_data.channels) * 255.0
    
def save_img_pixels(img_data: bpy.types.Image, img_mat):
    img_data.pixels = img_mat.ravel() / 255.0

def get_brush_tex_image(mode, is_mask=False):
    """Get the image data used by the current brush"""
    brush = None
    if mode == 'PAINT_TEXTURE':
        brush = bpy.context.tool_settings.image_paint.brush
    elif mode == 'SCULPT':
        brush = bpy.context.tool_settings.sculpt.brush
    elif mode == 'PAINT_VERTEX':
        brush = bpy.context.tool_settings.vertex_paint.brush
    if brush is None:
        return None, None
    
    tex = brush.texture if not is_mask else brush.mask_texture
    if tex is None or tex.type != 'IMAGE':
        return None, None
    return tex.image, tex

class CommonOptions:
    is_mask: bpy.props.BoolProperty(
        default=False
    )

class AlphaEdgeSoftenOperator(bpy.types.Operator, CommonOptions):
    """Set alpha values to texture pixels based on their distance from the contour of the image. This can reduce the height discontinuity when using the texture as a sculpting brush"""
    bl_idname = "paint_brush.alpha_soften"
    bl_label = "Alpha Edge Soften"
    bl_category = 'View'
    bl_options = {'REGISTER', 'UNDO'}  

    edge_pixels: bpy.props.IntProperty(
        name='Edge Width',
        description='',
        subtype='PIXEL',
        default=25, min=1, soft_max=100,
    ) 
    edge_style: bpy.props.EnumProperty(            
        name='Edge Style',
        items=[ ('LIN', 'Linear', ''),
               ('SPH', 'Sphere', ''),],
        default='SPH',
    ) 
    output_mode: bpy.props.EnumProperty(            
        name='Output Mode',
        items=[ ('REPLACE', 'Replace', ''),
               ('MUL', 'Multiply', ''),],
        default='MUL',
    )    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'edge_pixels')
        layout.prop(self, 'edge_style')
        layout.prop(self, 'output_mode')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)
        
    def execute(self, context):
        img_data, tex = get_brush_tex_image(context.mode, self.is_mask)
        if not img_data:
            return {'FINISHED'}
        img_data.reload()
        
        # Get inner and edge regions of the image using 3x3 convolution
        img_mat = load_img_pixels(img_data)
        alpha_mat = (img_mat[:,:,3] > 0).astype('uint8')
        edge_mat = alpha_mat.copy()
        edge_mat[1:-1, 1:-1] += (edge_mat[:-2,1:-1]+edge_mat[2:,1:-1]+edge_mat[1:-1,:-2]+edge_mat[1:-1,2:])
        edge_mat = np.logical_and((edge_mat > 0), (edge_mat < 5))
        
        # Set up KDTree for all edge points for lookup
        edge_points = []
        for u in range(edge_mat.shape[0]):
            for v in range(edge_mat.shape[1]):
                if edge_mat[u][v]:
                    edge_points.append((u, v, 0))
        kdt = kdtree.KDTree(len(edge_points))
        for i, co in enumerate(edge_points):
            kdt.insert(co, i)
        kdt.balance()
        
        # Find nearest edge point for each inside point
        for u in range(edge_mat.shape[0]):
            for v in range(edge_mat.shape[1]):
                if alpha_mat[u][v]:     
                    _, _, dist = kdt.find((u, v, 0))
                    if self.edge_style == 'LIN':
                        alpha_mat[u][v] = 255.0 * smoothstep(dist / self.edge_pixels)
                    elif self.edge_style == 'SPH':
                        alpha_mat[u][v] = 255.0 * np.sqrt(1 - (1 - dist / self.edge_pixels) ** 2) \
                                            if dist < self.edge_pixels else 255
                    
        # Set new alpha values
        if self.output_mode == 'REPLACE':
            img_mat[:,:,3] = alpha_mat
        elif self.output_mode == 'MUL':
            img_mat[:,:,3] = img_mat[:,:,3] * alpha_mat / 255.0
        save_img_pixels(img_data, img_mat)
        
        if tex.preview:
            tex.preview.reload()
        return {'FINISHED'}
    
class AlphaClipOperator(bpy.types.Operator, CommonOptions):
    """Set alpha values of pixels to either 0 or 1 according to a threshold"""
    bl_idname = "paint_brush.alpha_clip"
    bl_label = "Alpha Clip"
    bl_category = 'View'
    bl_options = {'REGISTER', 'UNDO'}  

    threshold: bpy.props.FloatProperty(
        name='Threshold',
        description='',
        default=0.5, min=0, max=1,
    ) 
    criterion: bpy.props.EnumProperty(            
        name='Criterion',
        items=[ ('ALPHA', 'Alpha', ''),
               ('VALUE', 'Color', ''),],
        default='ALPHA',
    )    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'criterion')
        layout.prop(self, 'threshold')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)
        
    def execute(self, context):
        img_data, tex = get_brush_tex_image(context.mode, self.is_mask)
        if not img_data:
            return {'FINISHED'}
        img_data.reload()
        
        img_mat = load_img_pixels(img_data)
        input_feature = img_mat[:,:,3]
        if self.criterion == 'VALUE':
            input_feature = 0.2126 * img_mat[:,:,0] + 0.7152 * img_mat[:,:,1] + 0.0722 * img_mat[:,:,2]
            
        img_mat[:,:,3] = input_feature > (self.threshold * 255.0)
        img_mat[:,:,3] *= 255.0
        save_img_pixels(img_data, img_mat)

        if tex.preview:
            tex.preview.reload()        
        return {'FINISHED'}
    
class ColorFillOperator(bpy.types.Operator, CommonOptions):
    """Recolor the image with a single color or double colors"""
    bl_idname = "paint_brush.color_fill"
    bl_label = "Color Fill"
    bl_category = 'View'
    bl_options = {'REGISTER', 'UNDO'}  

    fill_color: bpy.props.FloatVectorProperty(
        name = "Color",
        subtype = "COLOR",
        default = (1.0,1.0,1.0,1.0),
        min=0.0, max=1.0, size=4,
    )
    secondary_color: bpy.props.FloatVectorProperty(
        name = "Secondary Color",
        subtype = "COLOR",
        default = (.0,.0,.0,1.0),
        min=0.0, max=1.0, size=4,
    )
    threshold: bpy.props.FloatProperty(
        name='Threshold',
        description='Pixels darker than threshold will be filled with the secondary color',
        default=0.5, min=0, max=1,
    )
    duo_mode: bpy.props.BoolProperty(
        name='Duo Colors',
        default = False
    )
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'fill_color')
        layout.prop(self, 'duo_mode')
        if self.duo_mode:
            layout.prop(self, 'secondary_color')
            layout.prop(self, 'threshold')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)
        
    def execute(self, context):
        img_data, tex = get_brush_tex_image(context.mode, self.is_mask)
        if not img_data:
            return {'FINISHED'}
        img_data.reload()
        
        img_mat = load_img_pixels(img_data)
        if self.duo_mode:
            value_mat = 0.2126 * img_mat[:,:,0] + 0.7152 * img_mat[:,:,1] + 0.0722 * img_mat[:,:,2]
            threshold_mat = value_mat > (self.threshold * 255.0)
            threshold_mat = np.repeat(threshold_mat[:, :, np.newaxis], 3, axis=2)
            img_mat[:,:,:3] = self.fill_color[:3] * threshold_mat + self.secondary_color[:3] * (1-threshold_mat)
        else:
            img_mat[:,:,:3] = self.fill_color[:3]
        img_mat[:,:,:3] *= 255.0
        save_img_pixels(img_data, img_mat)
        
        if tex.preview:
            tex.preview.reload()
        return {'FINISHED'} 
    
class InvertChannelOperator(bpy.types.Operator, CommonOptions):
    """Invert color or alpha values of the image"""
    bl_idname = "paint_brush.invert"
    bl_label = "Invert"
    bl_category = 'View'
    bl_options = {'REGISTER', 'UNDO'}  

    invert_color: bpy.props.BoolProperty(
        name='Invert Color',
        default = True
    )
    invert_alpha: bpy.props.BoolProperty(
        name='Invert Alpha',
        default = False
    )
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'invert_color')
        layout.prop(self, 'invert_alpha')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)
        
    def execute(self, context):
        img_data, tex = get_brush_tex_image(context.mode, self.is_mask)
        if not img_data:
            return {'FINISHED'}
        img_data.reload()
        
        img_mat = load_img_pixels(img_data)
        if self.invert_alpha:
            img_mat[:,:,3] = 255.0 - img_mat[:,:,3]
        if self.invert_color:
            img_mat[:,:,:3] = 255.0 - img_mat[:,:,:3]
        save_img_pixels(img_data, img_mat)
        
        if tex.preview:
            tex.preview.reload()
        return {'FINISHED'}