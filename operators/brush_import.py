import os
import struct
import bpy
from bpy_extras.io_utils import ImportHelper
from ..brush_file_parsers import *

def brush_filter(brush: bpy.types.Brush, keyword):
    """Show users only the relevant brushes"""
    if keyword == 'TEXTURE':
        return brush.use_paint_image and brush.image_tool == 'DRAW'
    elif keyword == 'SCULPT':
        return brush.use_paint_sculpt and brush.sculpt_tool in {'DRAW', 'PAINT'}
    elif keyword == 'GPENCIL':
        return brush.use_paint_grease_pencil and brush.gpencil_tool == 'DRAW'
    elif keyword == 'VERTEX':
        return brush.use_paint_vertex and brush.vertex_tool == 'DRAW'
    return False

def new_gp_brush(name):
    """Creation of a new Grease Pencil brush should consider the difference between GPv2 and GPv3"""
    if bpy.app.version >= (4, 3, 0):
        res = bpy.data.brushes.new(name, mode='PAINT_GREASE_PENCIL')
        res.color = (0,0,0)
        res.gpencil_settings.vertex_color_factor = 1
        res.gpencil_settings.vertex_mode = 'BOTH'
        res.gpencil_settings.aspect = (1.0,1.0)
    else:
        src = [brush for brush in bpy.data.brushes if brush.use_paint_grease_pencil and brush.gpencil_tool=='DRAW']
        if len(src) < 1:
            return None
        res = src[0].copy()
        res.name = name
    return res

def set_brush_color_randomness(brush, attribute, value):
    """Depending on Blender verions, color randomness is available in different modes and also has different attribute names"""
    new_attr = f'{attribute}_jitter'
    if hasattr(brush, new_attr):
        setattr(brush, new_attr, value)

    legacy_attr = f'random_{attribute}_factor'
    if hasattr(brush, 'gpencil_settings') and hasattr(brush.gpencil_settings, legacy_attr):
        setattr(brush.gpencil_settings, legacy_attr, value)

class ImportBrushOperator(bpy.types.Operator, ImportHelper):
    """Extract textures from several painting software brush formats to create Blender brushes"""
    bl_idname = "paint_brush.import_brushes"
    bl_label = "Paint Brushes (.abr/.gbr/.brushset/.sut)"
    bl_category = 'View'
    bl_options = {'REGISTER', 'UNDO'}

    directory: bpy.props.StringProperty(subtype='DIR_PATH')
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement)
    filepath = bpy.props.StringProperty(name="File Path", subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default='*.gbr;*.gih;*.abr;*.brushset;*.brush;*.sut',
        options={'HIDDEN'}
    )
    brush_context_mode: bpy.props.EnumProperty(
        name='Mode',
        items=[('TEXTURE', 'Texture Paint', ''),
                ('SCULPT', 'Sculpt', ''),
                ('GPENCIL', 'Grease Pencil', ''),
                ('VERTEX', 'Vertex Paint', '')],
        default='TEXTURE'
    )    
    icon_save_path: bpy.props.EnumProperty(
        name='Save Icons/Images to',
        items=[('PROJECT', 'Folder of Blend File', ''),
                ('BRUSH', 'Folder of Brush File', ''),
                ('TMP', 'Temporary Folder', '')],
        default='BRUSH',
        description='The directory to save thumbnail images, which will be displayed as brush icons'
    )
    template_brush: bpy.props.StringProperty(
            name='Template Brush',
            description='If non-empty, copy attributes from an existing brush to create new ones',
            default='',
            search=lambda self, context, edit_text: [brush.name for brush in bpy.data.brushes if brush_filter(brush, self.brush_context_mode)]
    )
    use_random_rotation: bpy.props.BoolProperty(
        name='Random Rotation',
        default=True,
        description='If enabled, rotate the texture randomly for each drawn stroke point'
    )
    import_as_sequence: bpy.props.BoolProperty(
        name='Import Brush as Image Sequence',
        default=False,
        description='Import the brush to use with the add-on "Animated Texture Brush". If you do not have this add-on, please do not enable this option'
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text='Create New Brushes for:')
        layout.prop(self, 'brush_context_mode')
        layout.label(text='Template Brush:')
        layout.prop(self, 'template_brush', text="", icon='BRUSH_DATA')
        layout.prop(self, 'use_random_rotation')
        layout.label(text = 'Save Icons to: ')
        layout.prop(self, 'icon_save_path', text="")
        layout.prop(self, 'import_as_sequence')

    def execute(self, context):
        import numpy as np
             
        # Determine the location to save icons. Create a new folder if necessary
        if self.icon_save_path=='BRUSH':
            save_dir = self.directory
        elif self.icon_save_path=='PROJECT' and len(bpy.path.abspath('//'))>0:
            save_dir = bpy.path.abspath('//')
        else:
            save_dir = bpy.app.tempdir
        icon_dir = os.path.join(save_dir, 'bl_paint_brush_icons')
        if not os.path.exists(icon_dir):
            os.makedirs(icon_dir)
        if self.import_as_sequence:
            img_seq_dir = os.path.join(save_dir, 'bl_paint_brush_sequences')
            if not os.path.exists(img_seq_dir):
                os.makedirs(img_seq_dir)

        # Create objects in the following sequence:
        #    Grease Pencil mode:  Image -> Material -> Brush
        #    Other modes:         Image -> Texture -> Brush
        
        total_brushes = 0
        failures = 0
        for f in self.files:
            # Determine the software that generates the brush file
            filename = os.path.join(self.directory, f.name)
            fd = open(filename, 'rb')
            parser = None

            try:
                if f.name.endswith('.gbr'):  
                    parser = GbrParser(fd.read())
                elif f.name.endswith('.gih'):
                    parser = GihParser(fd.read())
                elif f.name.endswith('.abr'):
                    bytes = fd.read()
                    major_version = struct.unpack_from('>H',bytes)[0]
                    if major_version > 5:
                        parser = Abr6Parser(bytes)
                    else:
                        parser = Abr1Parser(bytes)
                elif f.name.endswith('.brushset') or f.name.endswith('.brush'):
                    parser = BrushsetParser(filename)
                elif f.name.endswith('.sut'):
                    parser = SutParser(filename)

                if not parser or not parser.check():
                    self.report({"ERROR"}, f"The brush file {f.name} cannot be recognized.")
                    continue
                parser.parse()
                
            except Exception as e:
                self.report({"ERROR"}, f"Failed to parse the brush file {f.name}: {e}")
                failures += 1
                continue

            total_brushes += len(parser.brush_mats)
            for i,brush_mat in enumerate(parser.brush_mats):
                if len(parser.brush_mats) == 1:
                    brush_name = f.name.split('.')[0]
                else:
                    brush_name = f.name.split('.')[0] + '_' + str(i)
                img_H, img_W = brush_mat.shape[0], brush_mat.shape[1]

                # Attempt to read original parameters data
                # Brushes with duo textures (usually a shape and a mask) should be marked
                orig_name, orig_params, orig_type = None, None, None
                if hasattr(parser, 'get_params'):
                    orig_name, orig_params = parser.get_params(i)
                    if orig_name:
                        brush_name = orig_name
                if hasattr(parser, 'is_tex_grain') and parser.is_tex_grain[i]:
                    orig_type = 'GRAIN'

                # Extract and convert an image texture
                if len(brush_mat.shape)==3:             # RGBA brush such as SUT and some GBR
                    image_mat = brush_mat.copy()
                    if isinstance(parser, SutParser):   # SUT brushes use black patterns while others use white
                        image_mat[:,:,:3] = 255 - image_mat[:,:,:3]
                else:
                    image_mat = brush_mat.reshape((img_H, img_W, 1)).repeat(4, axis=2)
                    # Invert the image alpha for several cases
                    if orig_params:
                        if orig_type == 'GRAIN' and \
                            'textureInverted' in orig_params and \
                            orig_params['textureInverted']:
                                image_mat = 255 - image_mat
                        if orig_type != 'GRAIN' and \
                            'shapeInverted' in orig_params and \
                            orig_params['shapeInverted']:
                                image_mat = 255 - image_mat
                                
                # Adjust the ratio of the texture to 1:1
                # Also need to fit image inside a round shape except for Grease Pencil mode
                img_L = max(img_H, img_W)
                if self.brush_context_mode != 'GPENCIL' and orig_type != 'GRAIN':
                    img_L = int(np.ceil(img_L * 1.415))
                offset_H, offset_W = (img_L-img_H)//2, (img_L-img_W)//2
                square_img_mat = np.zeros((img_L, img_L, 4))
                square_img_mat[offset_H:offset_H+img_H, offset_W:offset_W+img_W, :] = image_mat
                image_mat, img_H, img_W = square_img_mat, img_L, img_L
                    
                # Convert image to Blender data block
                brush_name += '.' + self.brush_context_mode
                img_obj = bpy.data.images.new(brush_name, img_W, img_H, alpha=True, float_buffer=False)
                img_pixels = np.flipud(image_mat).astype(np.float32).ravel() / 255.0
                img_obj.pixels.foreach_set(img_pixels)
                img_obj.alpha_mode = 'PREMUL'
                
                # In the image sequence mode, save all images, and generate only one brush by reloading images as a sequence
                # In other modes, pack the image into the .blend file
                if self.import_as_sequence:
                    seq_path = os.path.join(img_seq_dir, f'{f.name}.{(i+1):04d}.png')
                    img_obj.filepath_raw = seq_path
                    img_obj.save()
                    bpy.data.images.remove(img_obj)
                    
                    if i != len(parser.brush_mats)-1:
                        continue
                    else:
                        bpy.ops.image.open(
                            filepath=seq_path, directory=img_seq_dir,
                            files=[{"name":f'{f.name}.{(j+1):04d}.png'} for j in range(i+1)],
                            relative_path=True
                        )
                        img_obj = bpy.data.images[f'{f.name}.0001.png']
                else:
                    img_obj.pack()
                
                # Create a Blender texture
                if self.brush_context_mode != 'GPENCIL':
                    tex_obj = bpy.data.textures.new(brush_name, 'IMAGE')
                    tex_obj.image = img_obj
                    # Texture brush uses alpha, while others use the greyscale value
                    if self.brush_context_mode == 'TEXTURE':
                        tex_obj.use_alpha = True
                    else:
                        tex_obj.use_alpha = False
                    
                    if self.import_as_sequence:
                        tex_obj.image_user.use_auto_refresh = True
                        tex_obj.image_user.frame_duration = len(parser.brush_mats)
                        tex_obj.image_user.frame_start = 1
                        tex_obj.image_user.frame_offset = 0
                        tex_obj.image_user.use_cyclic = True
                        
                # Create a Blender Grease Pencil material
                else:
                    if orig_type == 'GRAIN':
                        brush_name = '(Grain) ' + brush_name
                        new_material = bpy.data.materials.new(brush_name)
                        bpy.data.materials.create_gpencil_data(new_material)
                        new_material.grease_pencil.show_stroke = False
                        new_material.grease_pencil.show_fill = True
                        new_material.grease_pencil.fill_style = 'TEXTURE'
                        new_material.grease_pencil.mix_factor = 1
                        new_material.grease_pencil.fill_image = img_obj
                    else:
                        new_material = bpy.data.materials.new(brush_name)
                        bpy.data.materials.create_gpencil_data(new_material)
                        new_material.grease_pencil.show_stroke = True
                        new_material.grease_pencil.mode = 'BOX'
                        new_material.grease_pencil.stroke_style = 'TEXTURE'
                        new_material.grease_pencil.mix_stroke_factor = 1
                        new_material.grease_pencil.stroke_image = img_obj
                    
                # Create a Blender brush
                template_brush_name = self.template_brush
                new_brush = None
                if self.template_brush != '':
                    new_brush = bpy.data.brushes[template_brush_name].copy()
                elif self.brush_context_mode == 'GPENCIL':
                    new_brush = new_gp_brush(brush_name)
                elif self.brush_context_mode == 'TEXTURE':
                    new_brush = bpy.data.brushes.new(brush_name, mode='TEXTURE_PAINT')
                elif self.brush_context_mode == 'SCULPT':
                    new_brush = bpy.data.brushes.new(brush_name, mode='SCULPT')
                elif self.brush_context_mode == 'VERTEX':
                    new_brush = bpy.data.brushes.new(brush_name, mode='VERTEX_PAINT')
                if new_brush is None:
                    self.report({"ERROR"}, f"Cannot create a new brush for {brush_name}.")
                    return {'FINISHED'}
                
                # Set basic parameters for the brush of different modes
                new_brush.name = brush_name
                if self.brush_context_mode == 'GPENCIL':
                    new_brush.gpencil_settings.use_material_pin = True
                    new_brush.gpencil_settings.material = new_material
                    new_brush.gpencil_settings.use_settings_random = self.use_random_rotation
                    new_brush.gpencil_settings.uv_random = 1.0
                    new_brush.gpencil_settings.hardness = 1.0
                    new_brush.gpencil_settings.simplify_factor = 0.0
                elif orig_type != 'GRAIN':
                    new_brush.texture = tex_obj
                    new_brush.texture_slot.map_mode = 'VIEW_PLANE'
                    new_brush.texture_slot.use_random = self.use_random_rotation
                else:
                    if self.brush_context_mode == 'TEXTURE':
                        new_brush.mask_texture = tex_obj
                        new_brush.mask_texture_slot.map_mode = 'TILED'
                    else:
                        new_brush.texture = tex_obj
                        new_brush.texture.map_mode = 'TILED'                        

                # Create an icon by scaling the brush texture down
                # TODO: possible changes required by Blender 5.0 that should be revisited after its release
                if hasattr(new_brush, 'use_custom_icon') and hasattr(new_brush, 'icon_filepath'):
                    new_brush.use_custom_icon = True
                    icon_name = f"icon_{self.brush_context_mode}_{f.name.split('.')[0]}_{i}"
                    if self.import_as_sequence:
                        icon_obj = bpy.data.images.new(icon_name, img_W, img_H, alpha=True, float_buffer=False)
                        icon_obj.pixels.foreach_set(img_pixels)
                    else:
                        icon_obj = img_obj.copy()
                        icon_obj.name = icon_name
                    icon_filepath = os.path.join(icon_dir, icon_obj.name+'.png')
                    icon_obj.filepath_raw = icon_filepath
                    icon_obj.scale(256,256)
                    icon_obj.save()
                    new_brush.icon_filepath = icon_filepath
                    bpy.data.images.remove(icon_obj)
                
                # Set asset information, necessary for Blender 4.3+
                new_brush.asset_generate_preview()
                new_brush.asset_mark()
                new_brush.asset_data.description = f'Converted from: {f.name}'

                # Parse and convert Photoshop brush parameters
                if isinstance(parser, Abr6Parser) and orig_params:
                    if 'brush' in orig_params:
                        if 'diameter' in orig_params['brush']:
                            new_brush.size = int(orig_params['brush']['diameter'].value)
                        if 'spacing' in orig_params['brush']:
                            new_brush.spacing = int(orig_params['brush']['spacing'].value)
                    if 'toolOptions' in orig_params:
                        if 'Opct' in orig_params['brush']:
                            new_brush.strength = orig_params['toolOptions']['Opct'].value * 0.01
                    if 'sizeControl' in orig_params:
                        if 'jitter' in orig_params['sizeControl']:
                            if self.brush_context_mode == 'GPENCIL':
                                new_brush.gpencil_settings.random_pressure = orig_params['sizeControl']['jitter'].value * 0.01
                    if 'opacityDynamics' in orig_params:
                        if 'jitter' in orig_params['opacityDynamics']:
                            if self.brush_context_mode == 'GPENCIL':
                                new_brush.gpencil_settings.random_strength = orig_params['opacityDynamics']['jitter'].value * 0.01
                    if 'hueJitter' in orig_params:
                        set_brush_color_randomness(new_brush, 'hue', orig_params['hueJitter'].value * 0.01)
                    if 'saturationJitter' in orig_params:
                        set_brush_color_randomness(new_brush, 'saturation', orig_params['saturationJitter'].value * 0.01)
                    if 'brightnessJitter' in orig_params:
                        set_brush_color_randomness(new_brush, 'value', orig_params['brightnessJitter'].value * 0.01)
                    
                # Parse and convert Procreate brush parameters
                if isinstance(parser, BrushsetParser) and orig_params:
                    if 'paintSize' in orig_params:
                        new_brush.size = int(500.0 * orig_params['paintSize'])
                    if 'textureScale' in orig_params:
                        if self.brush_context_mode == 'GPENCIL':
                            new_material.grease_pencil.texture_scale = (orig_params['textureScale'], orig_params['textureScale'])
                    if 'plotJitter' in orig_params:
                        if self.brush_context_mode == 'GPENCIL':
                            new_brush.gpencil_settings.pen_jitter = orig_params['plotJitter']
                        else:
                            new_brush.jitter = orig_params['plotJitter']
                    if 'plotSpacing' in orig_params:
                        if self.brush_context_mode == 'GPENCIL':
                            new_brush.gpencil_settings.input_samples = int(10 - 10 * orig_params['plotSpacing'])
                        else:
                            new_brush.spacing = int(100 * orig_params['plotSpacing'])
                    if 'paintOpacity' in orig_params:
                        if self.brush_context_mode == 'GPENCIL':
                            new_brush.gpencil_settings.pen_strength = orig_params['paintOpacity']
                        else:
                            new_brush.strength = orig_params['paintOpacity']
                    if 'dynamicsJitterSize' in orig_params:
                        if self.brush_context_mode == 'GPENCIL':
                            new_brush.gpencil_settings.random_pressure = orig_params['dynamicsJitterSize']
                    if 'dynamicsJitterOpacity' in orig_params:
                        if self.brush_context_mode == 'GPENCIL':
                            new_brush.gpencil_settings.random_strength = orig_params['dynamicsJitterOpacity']
                    if 'dynamicsJitterHue' in orig_params:
                        set_brush_color_randomness(new_brush, 'hue', orig_params['dynamicsJitterHue'])
                    if 'dynamicsJitterStrokeSaturation' in orig_params:
                        set_brush_color_randomness(new_brush, 'saturation', orig_params['dynamicsJitterStrokeSaturation'])
                    if 'dynamicsJitterStrokeDarkness' in orig_params:
                        set_brush_color_randomness(new_brush, 'value', orig_params['dynamicsJitterStrokeDarkness'])
                            
                # Parse and convert SUT brush parameters
                if isinstance(parser, SutParser) and orig_params:
                    if 'TextureScale2' in orig_params:
                        if self.brush_context_mode == 'GPENCIL':
                            new_material.grease_pencil.texture_scale = (orig_params['TextureScale2']/100.0, orig_params['TextureScale2']/100.0)
                    if 'BrushRotation' in orig_params:
                        if orig_params['BrushRotation'] > 1.0:
                            tex_angle = (orig_params['BrushRotation'] % 1.0) * np.pi / 2.0
                        else:
                            tex_angle = orig_params['BrushRotation'] * np.pi / 2.0
                        if self.brush_context_mode == 'GPENCIL':
                            new_material.grease_pencil.alignment_rotation = tex_angle
                        else:
                            new_brush.texture_slot.angle = tex_angle
                    if 'BrushSize' in orig_params:
                        new_brush.size = int(orig_params['BrushSize'])
                    if 'Opacity' in orig_params:
                        if self.brush_context_mode == 'GPENCIL':
                            new_brush.gpencil_settings.pen_strength = orig_params['Opacity'] / 100.0
                        else:
                            new_brush.strength = orig_params['Opacity'] / 100.0
                    if 'BrushHardness' in orig_params:
                        if self.brush_context_mode == 'GPENCIL':
                            new_brush.gpencil_settings.hardness = orig_params['BrushHardness'] / 100.0
                        else:
                            new_brush.hardness = orig_params['BrushHardness'] / 100.0
                    if 'BrushInterval' in orig_params:
                        if self.brush_context_mode == 'GPENCIL':
                            new_brush.gpencil_settings.input_samples = int(10 - orig_params['BrushInterval'] / 10.0)
                        else:
                            new_brush.spacing = int(orig_params['BrushInterval'])
                    if 'BrushChangePatternColor' in orig_params and orig_params['BrushChangePatternColor'] > 0:
                        if 'BrushHueChange' in orig_params:
                            set_brush_color_randomness(new_brush, 'hue', orig_params['BrushHueChange'] / 360.0)
                        if 'BrushSaturationChange' in orig_params:
                            set_brush_color_randomness(new_brush, 'saturation', orig_params['BrushSaturationChange'] / 100.0)
                        if 'BrushValueChange' in orig_params:
                            set_brush_color_randomness(new_brush, 'value', orig_params['BrushValueChange'] / 100.0)
            fd.close()
            
        if failures == 0:
            self.report({"INFO"}, f'Imported {total_brushes} brush texture(s).') 
        else:
            self.report({"WARNING"}, f'Imported {total_brushes} brush texture(s). Failed to recognize {failures} brush file(s).') 
        return {'FINISHED'}