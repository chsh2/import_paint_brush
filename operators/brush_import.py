import os
import struct
import bpy
from bpy_extras.io_utils import ImportHelper
from ..brush_file_parsers import *

def brush_filter(brush: bpy.types.Brush, keyword):
    """Show users only the relevant brushes"""

    def get_brush_type(brush, keyword):
        # API change in Blender 5.0
        legacy_attr = f'{keyword}_tool'
        new_attr = f'{keyword}_brush_type'
        if hasattr(brush, new_attr):
            return getattr(brush, new_attr)
        if hasattr(brush, legacy_attr):
            return getattr(brush, legacy_attr)

    if keyword == 'TEXTURE':
        return brush.use_paint_image and get_brush_type(brush, 'image') == 'DRAW'
    elif keyword == 'SCULPT':
        return brush.use_paint_sculpt and get_brush_type(brush, 'sculpt') in {'DRAW', 'PAINT'}
    elif keyword == 'GPENCIL':
        return brush.use_paint_grease_pencil and get_brush_type(brush, 'gpencil') == 'DRAW'
    elif keyword == 'VERTEX':
        return brush.use_paint_vertex and get_brush_type(brush, 'vertex') == 'DRAW'
    return False

def new_gp_brush(name, stroke_type="STROKE"):
    """Creation of a new Grease Pencil brush should consider the difference between GPv2 and GPv3"""
    if bpy.app.version >= (4, 3, 0):
        res = bpy.data.brushes.new(name, mode='PAINT_GREASE_PENCIL')
        res.color = (0,0,0)
        res.gpencil_settings.vertex_color_factor = 1
        res.gpencil_settings.vertex_mode = 'BOTH'
        res.gpencil_settings.aspect = (1.0,1.0)
        if hasattr(res.gpencil_settings, "stroke_type"):
            res.gpencil_settings.stroke_type = stroke_type
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
        brush.gpencil_settings.use_settings_random |= value > 1e-3
    
    if hasattr(brush, 'use_color_jitter'):
        brush.use_color_jitter |= value > 1e-3

def set_material_gpencil_rotation(mat, rad):
    """Fit any radian to [-pi/2, pi/2]"""
    v = rad % (2 * np.pi)
    if v >= 1.5 * np.pi:
        v -= 2 * np.pi
    elif v > 0.5 * np.pi:
        v -= np.pi
    mat.grease_pencil.alignment_rotation = v

class ImportBrushOperator(bpy.types.Operator, ImportHelper):
    """Extract textures from several painting software brush formats to create Blender brushes"""
    bl_idname = "paint_brush.import_brushes"
    bl_label = "Paint Brushes (.abr/.gbr/.brushset/.sut/.bundle)"
    bl_category = 'View'
    bl_options = {'REGISTER', 'UNDO'}

    directory: bpy.props.StringProperty(subtype='DIR_PATH')
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement)
    filepath = bpy.props.StringProperty(name="File Path", subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(
        default='*.gbr;*.gih;*.abr;*.brushset;*.brush;*.sut;*.kpp;*.bundle',
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
        description='The directory to save thumbnail images, which are required to display brush icons for lower versions of Blender'
    )
    pack_images: bpy.props.BoolProperty(
        name='Pack Images into Blend File',
        default=True,
        description='Pack the brush texture images into the .blend file, which may increase the file size. When disabled, save the image files to the selected location instead. If the option to import as an image sequence is enabled, the sequences cannot be packed and will always be saved outside'
    )
    template_brush: bpy.props.StringProperty(
        name='Template Brush',
        description='If non-empty, copy attributes from an existing brush for any attributes not specified or not parsed from the brush file',
        default='',
        search=lambda self, context, edit_text: [brush.name for brush in bpy.data.brushes if brush_filter(brush, self.brush_context_mode)]
    )
    use_random_rotation: bpy.props.BoolProperty(
        name='Random Rotation by Default',
        default=True,
        description='Determine whether to rotate the texture randomly for each drawn stroke point when the brush file itself does not specify it, or related attributes cannot be parsed'
    )
    krita_bundle_import_option: bpy.props.EnumProperty(
        name='Import Krita Bundles',
        items=[('TIPS', 'As GIMP Brushes', 'Extract and import .gih/.gbr files from the bundle'),
                ('PRESETS', 'As Krita Brushes', 'Extract .kpp brush presets from the bundle'),
                ],
        default='PRESETS',
        description='Choose how to interpret a Krita .bundle file'
    )
    import_as_sequence: bpy.props.BoolProperty(
        name='Animated Brush as Image Sequence',
        default=False,
        description='Create a multi-frame brush to use with the add-on "Animated Texture Brush". If you do not have this add-on, please do not enable this option. The multi-frame brush is a feature of .sut and .gih formats but not natively supported by Blender'
    )
    gpencil_dot_placement_mode: bpy.props.EnumProperty(
        name='Dot Placement Mode',
        items=[
            ('COUNT', 'Count', 'Place dots based on the drawing pace'),
            ('RADIUS', 'Radius', 'Place dots evenly along the stroke')
        ],
        default='COUNT',
        description='In Blender 5.2 or newer versions, Grease Pencil supports multiple ways to place dots along the drawn stroke. Earlier Blender versions ignore this option'
    )

    def draw(self, context):
        layout = self.layout

        current_template = self.template_brush
        if len(current_template) > 0 and (current_template not in bpy.data.brushes or not brush_filter(bpy.data.brushes[current_template], self.brush_context_mode)):
            self.template_brush = ''

        layout.label(text="Create New Brushes for:")
        layout.props_enum(self, 'brush_context_mode')

        layout.label(text='Attributes Parsing:')
        box = layout.box()
        row = box.row()
        row.label(text="Template Brush:")
        row.prop(self, 'template_brush', text="", icon='BRUSH_DATA')
        box.prop(self, 'use_random_rotation')

        layout.label(text="Per-Format Options:")
        box = layout.box()
        row = box.row()
        row.label(text="Import Krita Bundle: ")
        row.prop(self, 'krita_bundle_import_option', text="")
        box.prop(self, 'import_as_sequence')

        layout.label(text="Resource Management:")
        box = layout.box()
        row = box.row()
        row.label(text="Save Icons to: ")
        row.prop(self, 'icon_save_path', text="")
        box.prop(self, 'pack_images')

        if self.brush_context_mode == 'GPENCIL':
            layout.label(text="Grease Pencil Options:")
            box = layout.box()
            row = box.row()
            row.label(text="Dot Placement Mode: ")
            row.prop(self, 'gpencil_dot_placement_mode', text="")

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
        if not self.pack_images:
            img_tex_dir = os.path.join(save_dir, 'bl_paint_brush_textures')
            if not os.path.exists(img_tex_dir):
                os.makedirs(img_tex_dir)

        # Unarchive Krita bundles as separate brushes
        total_brushes = 0
        failures = 0
        brush_files = [(str(self.directory), str(f.name)) for f in self.files if not f.name.lower().endswith('.bundle')]
        for f in self.files:
            if not f.name.lower().endswith('.bundle'):
                continue
            bundle_processor = BundleProcessor(os.path.join(self.directory, f.name))
            if not bundle_processor.unarchive(bpy.app.tempdir):
                failures += 1
                continue
            if self.krita_bundle_import_option == 'TIPS':
                brush_files += bundle_processor.get_gimp_brush_files()
            else:
                brush_files += bundle_processor.get_kpp_brush_files()

        # Create objects in the following sequence:
        #    Grease Pencil mode:  Image -> Material -> Brush
        #    Other modes:         Image -> Texture -> Brush

        for d,f_name in brush_files:
            # Determine the software that generates the brush file
            filename = os.path.join(d, f_name)
            fd = open(filename, 'rb')
            parser = None

            try:
                if f_name.lower().endswith('.gbr'):
                    parser = GbrParser(fd.read())
                elif f_name.lower().endswith('.gih'):
                    parser = GihParser(fd.read())
                elif f_name.lower().endswith('.abr'):
                    bytes = fd.read()
                    major_version = struct.unpack_from('>H',bytes)[0]
                    if major_version > 5:
                        parser = Abr6Parser(bytes)
                    else:
                        parser = Abr1Parser(bytes)
                elif f_name.lower().endswith('.kpp'):
                    parser = KppParser(fd.read(), d)
                elif f_name.lower().endswith('.brushset') or f_name.lower().endswith('.brush'):
                    parser = BrushsetParser(filename)
                elif f_name.lower().endswith('.sut'):
                    parser = SutParser(filename)

                if not parser or not parser.check():
                    self.report({"ERROR"}, f"The brush file {f_name} cannot be recognized. Skipped this file.")
                    fd.close()
                    continue
                parser.parse()

            except Exception as e:
                self.report({"ERROR"}, f"Failed to parse the brush file {f_name}: {e}")
                failures += 1
                fd.close()
                continue

            total_brushes += len(parser.brush_mats)
            brush_data_mapping = {}
            for i,brush_mat in enumerate(parser.brush_mats):
                if len(parser.brush_mats) == 1:
                    brush_name = f_name.split('.')[0]
                else:
                    brush_name = f_name.split('.')[0] + '_' + str(i)
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
                        # For Brushset
                        if orig_type == 'GRAIN' and orig_params.get('textureInverted', False):
                            image_mat = 255 - image_mat
                        if orig_type != 'GRAIN' and orig_params.get('shapeInverted', False):
                            image_mat = 255 - image_mat
                        # For KPP
                        if orig_type == 'GRAIN' and orig_params.get('Texture/Pattern/Invert', False):
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
                    seq_path = os.path.join(img_seq_dir, f'{f_name}.{(i+1):04d}.png')
                    img_obj.filepath_raw = seq_path
                    img_obj.save()
                    bpy.data.images.remove(img_obj)

                    if i != len(parser.brush_mats)-1:
                        continue
                    else:
                        bpy.ops.image.open(
                            filepath=seq_path, directory=img_seq_dir,
                            files=[{"name":f'{f_name}.{(j+1):04d}.png'} for j in range(i+1)],
                            relative_path=True
                        )
                        img_obj = bpy.data.images[f'{f_name}.0001.png']
                else:
                    if self.pack_images:
                        img_obj.pack()
                    else:
                        img_path = os.path.join(img_tex_dir, f'{f_name}_{i:04d}.png')
                        img_obj.filepath_raw = img_path
                        img_obj.save()

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
                        new_material.grease_pencil.show_fill = False
                        new_material.grease_pencil.mode = 'BOX'
                        new_material.grease_pencil.stroke_style = 'TEXTURE'
                        if hasattr(new_material.grease_pencil, 'placement_mode'):
                            new_material.grease_pencil.placement_mode = self.gpencil_dot_placement_mode
                            new_material.grease_pencil.placement_count = 1
                        new_material.grease_pencil.mix_stroke_factor = 1
                        new_material.grease_pencil.stroke_image = img_obj

                # Create a Blender brush
                template_brush_name = self.template_brush
                new_brush = None
                if self.template_brush != '':
                    new_brush = bpy.data.brushes[template_brush_name].copy()
                elif self.brush_context_mode == 'GPENCIL':
                    new_brush = new_gp_brush(brush_name, 'FILL' if orig_type == 'GRAIN' else 'STROKE')
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
                elif orig_type == 'GRAIN':
                    if self.brush_context_mode == 'TEXTURE':
                        new_brush.mask_texture = tex_obj
                        new_brush.mask_texture_slot.map_mode = 'TILED'
                    else:
                        new_brush.texture = tex_obj
                        new_brush.texture_slot.map_mode = 'TILED'
                else:
                    new_brush.texture = tex_obj
                    new_brush.texture_slot.map_mode = 'VIEW_PLANE'
                    new_brush.texture_slot.use_rake = True
                    new_brush.texture_slot.use_random = self.use_random_rotation

                # Create an icon by scaling the brush texture down
                icon_name = f"icon_{self.brush_context_mode}_{f_name.split('.')[0]}_{i}"
                if self.import_as_sequence or not self.pack_images:
                    icon_obj = bpy.data.images.new(icon_name, img_W, img_H, alpha=True, float_buffer=False)
                    icon_obj.pixels.foreach_set(img_pixels)
                else:
                    icon_obj = img_obj.copy()
                    icon_obj.name = icon_name
                icon_filepath = os.path.join(icon_dir, icon_obj.name+'.png')
                icon_obj.filepath_raw = icon_filepath
                icon_obj.scale(256,256)
                icon_obj.save()

                # Setting icon for Blender 3.x/4.x
                if hasattr(new_brush, 'use_custom_icon') and hasattr(new_brush, 'icon_filepath'):
                    new_brush.use_custom_icon = True
                    new_brush.icon_filepath = icon_filepath
                    new_brush.asset_generate_preview()

                new_brush.asset_mark()
                new_brush.asset_data.description = f'Converted from: {f_name}'

                # Setting icon for Blender 5.x
                if bpy.app.version >= (5, 0, 0):
                    with bpy.context.temp_override(id=new_brush):
                        bpy.ops.ed.lib_id_load_custom_preview(filepath=icon_filepath)
                bpy.data.images.remove(icon_obj)

                # Parse and convert Photoshop brush parameters
                if isinstance(parser, Abr6Parser) and orig_params:
                    if 'brush' in orig_params:
                        if 'diameter' in orig_params['brush']:
                            new_brush.size = int(orig_params['brush']['diameter'].value)
                        if 'spacing' in orig_params['brush']:
                            new_brush.spacing = int(orig_params['brush']['spacing'].value / 2)
                        if 'angle' in orig_params['brush']:
                            converted_rad = orig_params['brush']['angle'].value * np.pi / 180.0
                            if self.brush_context_mode == 'GPENCIL':
                                set_material_gpencil_rotation(new_material, - converted_rad)
                            else:
                                new_brush.texture_slot.angle = (- converted_rad - np.pi / 2.0) % (2 * np.pi)

                    if 'toolOptions' in orig_params:
                        if 'Opct' in orig_params['toolOptions']:
                            if self.brush_context_mode == 'GPENCIL':
                                new_brush.gpencil_settings.pen_strength = orig_params['toolOptions']['Opct'].value * 0.01
                            new_brush.strength = orig_params['toolOptions']['Opct'].value * 0.01

                    if 'sizeControl' in orig_params:
                        if 'jitter' in orig_params['sizeControl']:
                            rand_factor = orig_params['sizeControl']['jitter'].value * 0.01
                            if self.brush_context_mode == 'GPENCIL':
                                new_brush.gpencil_settings.use_settings_random |= rand_factor > 1e-3
                                new_brush.gpencil_settings.random_pressure = rand_factor
                        if orig_params['sizeControl'].get('control', 0) == 2:
                            new_brush.use_pressure_size = True

                    if 'opacityDynamics' in orig_params:
                        if 'jitter' in orig_params['opacityDynamics']:
                            rand_factor = orig_params['opacityDynamics']['jitter'].value * 0.01
                            if self.brush_context_mode == 'GPENCIL':
                                new_brush.gpencil_settings.use_settings_random |= rand_factor > 1e-3
                                new_brush.gpencil_settings.random_strength = rand_factor
                        if orig_params['opacityDynamics'].get('control', 0) == 2:
                            new_brush.use_pressure_strength = True
                    
                    if 'angleDynamics' in orig_params:
                        if 'jitter' in orig_params['angleDynamics']:
                            rand_factor = orig_params['angleDynamics']['jitter'].value * 0.01
                            if self.brush_context_mode == 'GPENCIL':
                                new_brush.gpencil_settings.use_settings_random |= rand_factor > 1e-3
                                new_brush.gpencil_settings.uv_random = rand_factor
                            else:
                                new_brush.texture_slot.use_random |= rand_factor > 1e-3
                                new_brush.texture_slot.random_angle = rand_factor * 2 * np.pi

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
                        new_brush.spacing = int(100 * orig_params['plotSpacing'])
                    if 'paintOpacity' in orig_params:
                        if self.brush_context_mode == 'GPENCIL':
                            new_brush.gpencil_settings.pen_strength = orig_params['paintOpacity']
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
                    if 'shapeScatter' in orig_params:
                        rand_factor = orig_params['shapeScatter']
                        if self.brush_context_mode == 'GPENCIL':
                            new_brush.gpencil_settings.use_settings_random |= rand_factor > 1e-3
                            new_brush.gpencil_settings.uv_random = rand_factor
                        else:
                            new_brush.texture_slot.use_random |= rand_factor > 1e-3
                            new_brush.texture_slot.random_angle = rand_factor * 2 * np.pi
                    if self.brush_context_mode != 'GPENCIL':
                        new_brush.texture_slot.angle = 1.5 * np.pi

                # Parse and convert SUT brush parameters
                if isinstance(parser, SutParser) and orig_params:
                    # Spray mode overrides several parameters
                    sut_spray_mode = orig_params.get('BrushUseSpray', 0) > 0
                    rot_key = 'BrushRotationInSpray' if sut_spray_mode else 'BrushRotation'
                    rot_effector_key = 'BrushRotationEffectorInSpray' if sut_spray_mode else 'BrushRotationEffector'
                    rot_random_key = 'BrushRotationRandomInSpray' if sut_spray_mode else 'BrushRotationRandomScale'
                    size_key = 'BrushSpraySize' if sut_spray_mode else 'BrushSize'

                    sut_ribbon_mode = orig_params.get('BrushRibbon', 0) > 0
                    sut_rot_delta = np.pi / 2.0 if sut_ribbon_mode else 0.0

                    if rot_key in orig_params:
                        converted_rad = orig_params[rot_key] * np.pi / 180.0 + sut_rot_delta
                        if self.brush_context_mode == 'GPENCIL':
                            set_material_gpencil_rotation(new_material, converted_rad)
                        else:
                            new_brush.texture_slot.angle = (converted_rad - np.pi / 2.0) % (2 * np.pi)
                    if orig_params.get(rot_effector_key, 0) >= 128:
                        if rot_random_key in orig_params:
                            rand_factor = orig_params[rot_random_key] / 100.0
                            if self.brush_context_mode == 'GPENCIL':
                                new_brush.gpencil_settings.use_settings_random |= rand_factor > 1e-3
                                new_brush.gpencil_settings.uv_random = rand_factor
                            else:
                                new_brush.texture_slot.use_random |= rand_factor > 1e-3
                                new_brush.texture_slot.random_angle = rand_factor * 2 * np.pi
                    if size_key in orig_params:
                        new_brush.size = int(orig_params[size_key])
                    
                    if sut_spray_mode:
                        if 'BrushSprayBias' in orig_params:
                            converted_factor = - orig_params['BrushSprayBias'] / 200.0 + 0.5
                            if self.brush_context_mode == 'GPENCIL':
                                new_brush.gpencil_settings.use_settings_random |= converted_factor > 1e-3
                                new_brush.gpencil_settings.pen_jitter = converted_factor / 2.0
                            else:
                                new_brush.jitter = converted_factor / 2.0

                    if 'Opacity' in orig_params:
                        if self.brush_context_mode == 'GPENCIL':
                            new_brush.gpencil_settings.pen_strength = orig_params['Opacity'] / 100.0
                        new_brush.strength = orig_params['Opacity'] / 100.0
                    if 'BrushHardness' in orig_params:
                        if self.brush_context_mode == 'GPENCIL':
                            new_brush.gpencil_settings.hardness = orig_params['BrushHardness'] / 100.0
                        else:
                            new_brush.hardness = orig_params['BrushHardness'] / 100.0
                    if 'BrushInterval' in orig_params:
                        new_brush.spacing = int(orig_params['BrushInterval'])
                    if 'BrushChangePatternColor' in orig_params and orig_params['BrushChangePatternColor'] > 0:
                        if 'BrushHueChange' in orig_params:
                            set_brush_color_randomness(new_brush, 'hue', orig_params['BrushHueChange'] / 360.0)
                        if 'BrushSaturationChange' in orig_params:
                            set_brush_color_randomness(new_brush, 'saturation', orig_params['BrushSaturationChange'] / 100.0)
                        if 'BrushValueChange' in orig_params:
                            set_brush_color_randomness(new_brush, 'value', orig_params['BrushValueChange'] / 100.0)

                    if sut_ribbon_mode:
                        new_brush.spacing = 50
                        if self.brush_context_mode == 'GPENCIL':
                            new_brush.gpencil_settings.uv_random = 0.0
                        else:
                            new_brush.texture_slot.random_angle = 0.0

                # Parse and convert KPP brush parameters: most parameters are texts
                if isinstance(parser, KppParser) and orig_params:
                    if 'brush_definition/scale' in orig_params:
                        converted_size = float(orig_params['brush_definition/scale']) * orig_params['KPP_BRUSH_SIZE']
                        if 'SizeValue' in orig_params:
                            converted_size *= float(orig_params['SizeValue'])
                        new_brush.size = max(int(converted_size), 1)

                    if 'brush_definition/spacing' in orig_params:
                        converted_spacing = float(orig_params['brush_definition/spacing'])
                        if orig_params.get('brush_definition/useAutoSpacing', '0') != '0':
                            converted_spacing = float(orig_params.get('brush_definition/autoSpacingCoeff', converted_spacing))
                            if converted_spacing > 1.0:
                                converted_spacing = np.sqrt(converted_spacing)
                        new_brush.spacing = max(int(50 * converted_spacing), 1)

                    if 'brush_definition/angle' in orig_params:
                        converted_rad = float(orig_params['brush_definition/angle'])
                        if self.brush_context_mode == 'GPENCIL':
                            set_material_gpencil_rotation(new_material, - converted_rad)
                        else:
                            new_brush.texture_slot.angle = (- converted_rad - np.pi / 2.0) % (2 * np.pi)

                    if 'PressureSize' in orig_params and orig_params['PressureSize'] == 'true':
                        if 'SizeValue' in orig_params:
                            factor = float(orig_params['SizeValue'])
                            new_brush.size = max(int(factor * new_brush.size), 1)
                        if 'SizeSensor' in orig_params:
                            new_brush.use_pressure_size = (orig_params['SizeSensor'].find("pressure") != -1)

                    if 'PressureOpacity' in orig_params and orig_params['PressureOpacity'] == 'true':
                        if 'OpacityValue' in orig_params:
                            if self.brush_context_mode == 'GPENCIL':
                                new_brush.gpencil_settings.pen_strength = float(orig_params['OpacityValue'])
                            new_brush.strength = float(orig_params['OpacityValue'])
                        if 'OpacitySensor' in orig_params:
                            new_brush.use_pressure_strength = (orig_params['OpacitySensor'].find("pressure") != -1)

                    if 'PressureRotation' in orig_params and orig_params['PressureRotation'] == 'true':
                        if 'RotationValue' in orig_params:
                            rand_factor = float(orig_params['RotationValue'])
                            if 'RotationSensor' in orig_params:
                                if orig_params['RotationSensor'].find("fuzzy") == -1:
                                    rand_factor = 0
                            if self.brush_context_mode == 'GPENCIL':
                                new_brush.gpencil_settings.use_settings_random |= rand_factor > 1e-3
                                new_brush.gpencil_settings.uv_random = rand_factor
                            else:
                                new_brush.texture_slot.use_random |= rand_factor > 1e-3
                                new_brush.texture_slot.random_angle = rand_factor * 2 * np.pi

                    if 'PressureScatter' in orig_params and orig_params['PressureScatter'] == 'true':
                        if 'ScatterValue' in orig_params:
                            rand_factor = float(orig_params['ScatterValue'])
                            if self.brush_context_mode == 'GPENCIL':
                                new_brush.gpencil_settings.use_settings_random |= rand_factor > 1e-3
                                new_brush.gpencil_settings.pen_jitter = rand_factor / 2.0
                            else:
                                new_brush.jitter = rand_factor / 2.0
                        if 'ScatterSensor' in orig_params:
                            if self.brush_context_mode == 'GPENCIL':
                                new_brush.gpencil_settings.use_jitter_pressure = (orig_params['ScatterSensor'].find("pressure") != -1)
                            else:
                                new_brush.use_pressure_jitter = (orig_params['ScatterSensor'].find("pressure") != -1)
            
                # Post-processing for certain parameters
                if self.brush_context_mode == 'GPENCIL':
                    # Blender 5.1+: Grease Pencil stroke placement
                    if hasattr(new_material.grease_pencil, 'placement_radius_spacing'):
                        new_material.grease_pencil.placement_radius_spacing = new_brush.spacing
                    new_brush.gpencil_settings.input_samples = max(int(10 - new_brush.spacing / 20.0), 1)

                if (orig_name, orig_type) not in brush_data_mapping:
                    brush_data_mapping[(orig_name, orig_type)] = []
                brush_data_mapping[(orig_name, orig_type)].append(new_brush)

            # Texture paint mode can use both a texture and a mask at the same time
            if self.brush_context_mode == 'TEXTURE':
                for (grain_name, grain_type), grain_brushes in brush_data_mapping.items():
                    if grain_type == 'GRAIN' and len(grain_brushes) > 0:
                        grain_brush = grain_brushes[0]
                        for (orig_name, orig_type), tex_brushes in brush_data_mapping.items():
                            if orig_name == grain_name and orig_type != 'GRAIN':
                                for tex_brush in tex_brushes:
                                    tex_brush.mask_texture = grain_brush.mask_texture
                                    tex_brush.mask_texture_slot.map_mode = 'TILED'

            fd.close()

        if failures == 0:
            self.report({"INFO"}, f'Imported {total_brushes} brush texture(s).')
        else:
            self.report({"WARNING"}, f'Imported {total_brushes} brush texture(s). Failed to recognize {failures} brush file(s).')
        return {'FINISHED'}
