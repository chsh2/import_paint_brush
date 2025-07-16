import struct
import numpy as np

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
