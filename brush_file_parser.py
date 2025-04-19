import struct
import numpy as np

abr_skipped_bytes = {1: 47, 2: 301}

def rle_decode(bytes, img_H, img_W, depth):
    """
    This function follows the Photoshop specification as stated below:
        The image data starts with the byte counts for all the scan lines in the channel (LayerBottom-LayerTop), 
        with each count stored as a two-byte value.
        The RLE compressed data follows, with each scan line compressed separately.
    """
    dtype = '>u'+str(depth//8)
    img_mat = np.zeros((img_H, img_W), dtype=dtype)
    line_byte_count = np.frombuffer(bytes, dtype='>u2', count=img_H)
    offset = img_H * 2
    
    for i in range(img_H):
        end_position = offset + line_byte_count[i]
        j = 0
        while offset < end_position:
            n = struct.unpack_from('>B', bytes, offset)[0]
            offset += 1
            if n == 128:
                continue
            elif n < 128:       # Non-compressed (n+1) numbers
                img_mat[i][j:j+n+1] = np.frombuffer(bytes, dtype=dtype, count=n+1, offset=offset)
                offset += (n+1)*(depth//8)
                j += (n+1)
            else:               # One number repeated (n+1) times
                n = (256-n)
                img_mat[i][j:j+n+1] = np.frombuffer(bytes, dtype=dtype, count=1, offset=offset)
                offset += (depth//8)
                j += (n+1)
    return img_mat

class Abr6Parser:
    """
    Parse bytes from an ABR file with main version 6/7 and minor version 1/2.
    This is not an open format, therefore only limited information can be extracted.
    Some references:
        http://fileformats.archiveteam.org/wiki/Photoshop_brush
        https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/PhotoshopFileFormats.htm#VirtualMemoryArrayList
        https://github.com/GNOME/gimp/blob/master/app/core/gimpbrush-load.c 
    """
    
    def unpack(self, format_string):
        """Get the values of one or more fields"""
        length = struct.calcsize(format_string)
        res = struct.unpack(format_string, self.bytes[self.offset: self.offset+length])
        self.offset += length
        return res if len(res)>1 else res[0]        
        
    def __init__(self, bytes):
        self.bytes = bytes
        self.offset = 0
        self.brush_mats = []
        self.major_version, self.minor_version = self.unpack('>HH')
        self.identifier, self.block_name = self.unpack('>4s4s')  # b'8BIM', b'samp'
    
    def check(self):
        """Whether the file format is supported"""
        if self.minor_version != 1 and self.minor_version != 2:
            return False
        if self.identifier != b'8BIM' or self.block_name != b'samp':
            return False
        return True
    
    def process_one_brush(self, byte_length):
        """Extract image matrix of one brush"""
        self.offset += abr_skipped_bytes[self.minor_version]    # Some unknown or unnecessary data
        top, left, bottom, right = self.unpack('>IIII')
        depth, compression = self.unpack('>HB')
        
        # Fill pixels in a NumPy array
        img_H, img_W = bottom-top, right-left
        dtype='>u'+str(depth//8)
        
        if compression==0:      # No compression
            pixels_1d = np.frombuffer(self.bytes, dtype=dtype, count=img_H*img_W, offset=self.offset)
            self.brush_mats.append(pixels_1d.reshape((img_H,img_W)))
    
        elif compression==1:    # RLE compression
            self.brush_mats.append(rle_decode(self.bytes[self.offset:self.offset+byte_length], img_H, img_W, depth))        
                
    def parse(self):
        samp_block_length = self.unpack('>I')
        end_position = self.offset + samp_block_length
        
        # Process brushes one by one and reset the offset value in between
        while self.offset < end_position:
            new_brush_length = self.unpack('>I')
            if new_brush_length % 4:
                new_brush_length += (4 - new_brush_length % 4)
            next_offset = self.offset + new_brush_length
            self.process_one_brush(new_brush_length)
            self.offset = next_offset

class Abr1Parser:
    """
    Parse bytes from an ABR file with main version 1/2.
    Only sampled brushes will be extracted, and the computed brushes will be ignored.
    """
    
    def unpack(self, format_string):
        """Get the values of one or more fields"""
        length = struct.calcsize(format_string)
        res = struct.unpack(format_string, self.bytes[self.offset: self.offset+length])
        self.offset += length
        return res if len(res)>1 else res[0]        
        
    def __init__(self, bytes):
        self.bytes = bytes
        self.offset = 0
        self.brush_mats = []
        self.major_version = self.unpack('>H')
        self.num_brushes = self.unpack('>H')
    
    def check(self):
        """Whether the file format is supported"""
        if self.major_version != 1 and self.major_version != 2:
            return False
        return True
    
    def process_one_brush(self, byte_length):
        """Extract image matrix of one brush"""
        self.offset += 6     # Some unknown or unnecessary data
        if self.major_version == 2:
            name_length = self.unpack('>I')
            self.offset += name_length * 2
        self.offset += 9
        top, left, bottom, right = self.unpack('>IIII')
        depth, compression = self.unpack('>HB')
        
        # Fill pixels in a NumPy array
        img_H, img_W = bottom-top, right-left
        dtype='>u'+str(depth//8)
        
        if img_H > 16384:       # Segmented image data is not supported
            return
        
        if compression==0:      # No compression
            pixels_1d = np.frombuffer(self.bytes, dtype=dtype, count=img_H*img_W, offset=self.offset)
            self.brush_mats.append(pixels_1d.reshape((img_H,img_W)))
            
        elif compression==1:    # RLE compression
            self.brush_mats.append(rle_decode(self.bytes[self.offset:self.offset+byte_length], img_H, img_W, depth))        
                
    def parse(self):
        for i in range(self.num_brushes):
            brush_type, brush_size = self.unpack('>HI')
            if brush_type != 2:     # Type is not supported
                self.offset += brush_size
            else:
                next_offset = self.offset + brush_size
                self.process_one_brush(brush_size)
                self.offset = next_offset  
 
class GbrParser:
    """
    Parse bytes from an GBR file with Version 2 according to:
        https://github.com/GNOME/gimp/blob/gimp-2-10/devel-docs/gbr.txt
    """
    
    def unpack(self, format_string):
        """Get the values of one or more fields"""
        length = struct.calcsize(format_string)
        res = struct.unpack(format_string, self.bytes[self.offset: self.offset+length])
        self.offset += length
        return res if len(res)>1 else res[0]        
        
    def __init__(self, bytes, offset=0):
        self.bytes = bytes
        self.offset = offset
        self.brush_mats = []        # Single element, either (height, width) or (height, width, 4)
        header_size = self.unpack('>I')
        self.version = self.unpack('>I')
        self.width, self.height, self.num_channels = self.unpack('>III')
        self.magic_number = self.unpack('>4s')  # b'GIMP'
        self.offset = offset + header_size      # Skip the rest fields
    
    def check(self):
        """Whether the file format is supported"""
        if self.version != 2 or self.magic_number != b'GIMP':
            return False
        return True
                 
    def parse(self):
        if self.num_channels == 1:
            pixels_1d = np.frombuffer(self.bytes, dtype='>u1', count=self.width*self.height, offset=self.offset)
            self.brush_mats.append(pixels_1d.reshape((self.height,self.width)))
        else:
            pixels_1d = np.frombuffer(self.bytes, dtype='>u1', count=self.width*self.height*self.num_channels, offset=self.offset)
            self.brush_mats.append(pixels_1d.reshape((self.height,self.width,self.num_channels)))  

class GihParser():
    """
    GIH file is the concatenation of multiple GBR brushes:
        https://developer.gimp.org/core/standards/gih/
    """
    def __init__(self, bytes, offset=0):
        self.bytes = bytes
        self.brush_mats = []
        self.name = ""
        
    def check(self):
        """"A valid GIH file contains the name and brush count in the first two lines"""
        contents = self.bytes.split(b"\n")
        if len(contents) < 3:
            return False
        self.name = contents[0].decode('utf-8')
        self.header_size = len(contents[0]) + len(contents[1]) + 2
        try:
            self.count = int(contents[1].decode('utf-8').split(' ')[0])
        except:
            return False
        return True
    
    def parse(self):
        """Call GbrParser multiple times to parse each brush"""
        self.bytes = self.bytes[self.header_size:]
        offset = 0
        for i in range(self.count):
            gbr_parser = GbrParser(self.bytes, offset)
            gbr_parser.parse()
            self.brush_mats.append(gbr_parser.brush_mats[0])
            offset = gbr_parser.offset + gbr_parser.width * gbr_parser.height * gbr_parser.num_channels
                    
    def get_params(self, i):
        """Currently only the brush name is available"""
        return self.name, None

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
            tmp_filepath = os.path.join(cache_dir, f"{brush_name}.png") 
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
