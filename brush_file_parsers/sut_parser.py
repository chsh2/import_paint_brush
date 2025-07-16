import uuid
import numpy as np

class SutParser():
    """
    Parse textures and paramters from .sut files through sqlite
    """
    def __init__(self, filename):
        self.filename = filename
        self.brush_mats = []
        self.params = []
    
    def check(self):
        # Some brush files do not contain any texture, which cannot be imported
        import sqlite3
        con = sqlite3.connect(self.filename)
        cur = con.cursor()
        try:
            res = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='MaterialFile'").fetchall()
        except:
            con.close()
            return False
        con.close()        
        return len(res) > 0
    
    def parse(self):
        import os, sqlite3, bpy
        from bpy_extras import image_utils
        cache_dir = bpy.app.tempdir
                
        con = sqlite3.connect(self.filename)
        cur = con.cursor()

        # Get brush parameters as a map. There should be a single brush
        res = cur.execute("SELECT * FROM Variant")
        param_values = res.fetchall()[0]
        param_names = res.description
        self.params.append({name[0]:value for name,value in zip(param_names, param_values) if value != None})
        # Get brush name
        res = cur.execute("SELECT NodeName FROM Node")
        brush_name = res.fetchone()[0]
        self.params[0]['BrushName'] = brush_name

        # Get image data encoded in PNG
        res = cur.execute("SELECT FileData FROM MaterialFile").fetchall()
        for img_bytes in res:
            # Only the last PNG block is a valid texture
            start_pos = []
            end_pos = []
            pos = 0
            while pos >= 0:
                start_pos.append(pos)
                pos = img_bytes[0].find(b'PNG', pos+1)
            pos = 0
            while pos >= 0:
                end_pos.append(pos)
                pos = img_bytes[0].find(b'IEND', pos+1)      
            tmp_filepath = os.path.join(cache_dir, f"{uuid.uuid4()}.png") 
            with open(tmp_filepath, 'wb') as tmp_file:
                tmp_file.write(img_bytes[0][start_pos[-1]-1:end_pos[-1]+8])
            
            # Extract pixels from PNG to 3D array
            img_obj = image_utils.load_image(tmp_filepath, check_existing=True)
            img_W = img_obj.size[0]
            img_H = img_obj.size[1]
            img_mat = np.array(img_obj.pixels).reshape(img_H,img_W, img_obj.channels)
            img_mat = np.flipud(img_mat) * 255
            self.brush_mats.append(img_mat)
            bpy.data.images.remove(img_obj)
        con.close()
            
    def get_params(self, i):
        """Return the brush name and parameters. Always return the first slot since all textures share the same set of parameters"""
        return self.params[0]['BrushName'], self.params[0]
