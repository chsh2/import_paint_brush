import numpy as np

class BrushsetParser():
    """
    Parse archived textures of Procreate brushes
    """
    def __init__(self, filename):
        self.filename = filename
        self.brush_mats = []
        self.is_tex_grain = []  # A unique type of texture defined in Procreate
        self.params = []
    
    def check(self):
        import zipfile
        return zipfile.is_zipfile(self.filename)
    
    def parse(self):
        import zipfile, os, plistlib, bpy
        from bpy_extras import image_utils

        # Uncompress texture files to the temporary folder
        cache_dir = bpy.app.tempdir
        tex_paths = []
        with zipfile.ZipFile(self.filename) as archive:
            namelist = archive.namelist()
            for member in namelist:
                if member.find('Reset') != -1:
                    continue
                elif member.endswith('Shape.png') or member.endswith('Grain.png'):
                    tex_paths.append(member)
                    self.is_tex_grain.append(member.endswith('Grain.png'))
                    self.params.append({})
                    
                    # Try to find the brush parameter file
                    param_path = member[:-9] + 'Brush.archive'
                    if param_path in namelist:
                        with archive.open(param_path) as param_file:
                            tmp_map = plistlib.load(param_file)
                            self.params[-1] = {key:value for key, value in tmp_map.items() if value != None}
                    brush_id = member[:-10]
                    self.params[-1]['identifier'] = brush_id
            for member in tex_paths:
                archive.extract(member, cache_dir)
                
        # Process each texture image file
        # The images loaded in Blender here are just for extracting the pixels
        # Final brush textures are generated not from this parser, but the operator
        for path in tex_paths:
            img_obj = image_utils.load_image(os.path.join(cache_dir, path), check_existing=True)
            img_W = img_obj.size[0]
            img_H = img_obj.size[1]
            img_mat = np.array(img_obj.pixels).reshape(img_H,img_W, img_obj.channels)
            img_mat = np.flipud(img_mat[:,:,0]) * 255
            self.brush_mats.append(img_mat)
            bpy.data.images.remove(img_obj)
            
    def get_params(self, i):
        """Return the name and parameters of i-th brush"""
        if self.params[i] == None or '$objects' not in self.params[i]:
            return None, None
        
        parsed_strings = []
        parsed_params = None
        for field in self.params[i]['$objects']:
            # Find all text information.
            if isinstance(field, str) and \
                not field.startswith(('$', '{')) and \
                not field.endswith(('.png','.jpg','.jpeg')):
                parsed_strings.append(field)
            # Find the big dictionary that stores parameters
            if isinstance(field, dict) and 'paintSize' in field:
                parsed_params = field
        parsed_name = parsed_strings[0] if len(parsed_strings)>0 else None
        return parsed_name, parsed_params
