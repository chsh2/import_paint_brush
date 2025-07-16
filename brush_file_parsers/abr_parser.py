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
 