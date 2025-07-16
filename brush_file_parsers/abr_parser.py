import struct
import numpy as np

def tag_as_u4(b):
    return struct.unpack(">I", b)[0]

TAG_8BIM = tag_as_u4(b"8BIM")

SUBTAG_SAMP = tag_as_u4(b"samp")
SUBTAG_DESC = tag_as_u4(b"desc")

TYPE_DESCRIPTOR = tag_as_u4(b"Objc")
TYPE_TEXT = tag_as_u4(b"TEXT")
TYPE_LIST = tag_as_u4(b"VlLs")
TYPE_UNIT_FLOAT = tag_as_u4(b"UntF")
TYPE_BOOL = tag_as_u4(b"bool")
TYPE_ENUMERATED = tag_as_u4(b"enum")
TYPE_INTEGER = tag_as_u4(b"long")
TYPE_DOUBLE = tag_as_u4(b"doub")

UNIT_ANGLE = tag_as_u4(b"#Ang")
UNIT_DENSITY = tag_as_u4(b"#Rsl")
UNIT_DISTANCE = tag_as_u4(b"#Rlt")
UNIT_NONE = tag_as_u4(b"#Nne")
UNIT_PERCENT = tag_as_u4(b"#Prc")
UNIT_PIXELS = tag_as_u4(b"#Pxl")

unit_names = {
    UNIT_ANGLE: "angle",
    UNIT_DENSITY: "density",
    UNIT_DISTANCE: "distance",
    UNIT_NONE: "",
    UNIT_PERCENT: "percent",
    UNIT_PIXELS: "pixels"
}

# From https://community.kde.org/Krita/Photoshop_Mapping_Table
property_names = {
    tag_as_u4(b"Brsh"): "brush",
    tag_as_u4(b"Nm  "): "name",
    tag_as_u4(b"Dmtr"): "diameter",
    tag_as_u4(b"Angl"): "angle",
    tag_as_u4(b"Rndn"): "roundness",
    tag_as_u4(b"Spcn"): "spacing",
    tag_as_u4(b"Intr"): "smoothing",
    tag_as_u4(b"szVr"): "sizeControl",
    tag_as_u4(b"bVTy"): "control",
    tag_as_u4(b"fStp"): "fadeStep",
    tag_as_u4(b"Wtdg"): "wetEdges",
    tag_as_u4(b"Nose"): "noise",
    tag_as_u4(b"Rpt "): "airbrush",
    tag_as_u4(b"BlnM"): "blendMode",
    tag_as_u4(b"Cnt "): "count",
    tag_as_u4(b"prVr"): "flowDynamics",
    tag_as_u4(b"opVr"): "opacityDynamics",
    tag_as_u4(b"wtVr"): "wetnessDynamics",
    tag_as_u4(b"mxVr"): "mixDynamics",
    tag_as_u4(b"clVr"): "colorDynamics",
    tag_as_u4(b"InvT"): "invertTexture",
    tag_as_u4(b"Txtr"): "texture",
    tag_as_u4(b"TxtC"): "textureEachTip",
    tag_as_u4(b"Mnm "): "minimum",
    tag_as_u4(b"Idnt"): "identifier",
    tag_as_u4(b"H   "): "hueJitter",
    tag_as_u4(b"Strt"): "saturationJitter",
    tag_as_u4(b"Brgh"): "brightnessJitter",
}

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
        end_position = offset + int(line_byte_count[i])
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

class UnitFloat:
    def __init__(self, unit, value):
        self.unit = unit
        self.value = value

    def __repr__(self):
        if self.unit == UNIT_NONE:
            return str(self.value)
        
        return str(self.value) + " (" + unit_names[self.unit] + ")"
    
    def __float__(self):
        return self.value

class Abr6Parser:
    """
    Parse bytes from an ABR file with main version 6/7 and minor version 1/2.
    This is not an open format, therefore only limited information can be extracted.
    Some references:
        http://fileformats.archiveteam.org/wiki/Photoshop_brush
        https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/PhotoshopFileFormats.htm#VirtualMemoryArrayList
        https://github.com/GNOME/gimp/blob/master/app/core/gimpbrush-load.c
        https://github.com/jlai/brush-viewer/blob/main/shared/abr/ABR.ksy
    """
    
    def unpack(self, format_string, peek = False):
        """Get the values of one or more fields"""
        length = struct.calcsize(format_string)
        res = struct.unpack(format_string, self.bytes[self.offset: self.offset+length])
        if not peek:
            self.offset += length
        return res if len(res)>1 else res[0]
        
    def __init__(self, bytes):
        self.bytes = bytes
        self.offset = 0
        self.brush_mats = []
        self.sample_ids = []
        self.brush_properties = {}
        self.major_version, self.minor_version = self.unpack('>HH')
        self.identifier, self.block_name = self.unpack('>4s4s', peek=True)  # b'8BIM', b'samp'

        self.desc_parsers = {
            TYPE_DESCRIPTOR: self.parse_descriptor,
            TYPE_TEXT: self.parse_unicode_string,
            TYPE_LIST: self.parse_list,
            TYPE_UNIT_FLOAT: self.parse_float,
            TYPE_BOOL: self.parse_bool,
            TYPE_INTEGER: self.parse_int,
            TYPE_DOUBLE: self.parse_double,
            TYPE_ENUMERATED: self.parse_enum
        }
    
    def check(self):
        """Whether the file format is supported"""
        if self.minor_version != 1 and self.minor_version != 2:
            return False
        if self.identifier != b'8BIM' or self.block_name != b'samp':
            return False
        return True


    def parse(self):
        """Parse the entire file"""
        while self.offset < len(self.bytes):
            (tag, subtag, length) = self.unpack('>III')
            next_offset = self.offset + length + (-length % 4)
            
            if tag == TAG_8BIM:
                if subtag == SUBTAG_SAMP:
                    self.parse_samples_block(next_offset)
                elif subtag == SUBTAG_DESC:
                    self.parse_descriptors_block()

            self.offset = next_offset

    def parse_samples_block(self, end_of_section):
        while self.offset < end_of_section:
            sample_length = self.unpack('>I')
            next_offset = self.offset + sample_length + (-sample_length % 4)
            self.parse_one_sample(sample_length)
            self.offset = next_offset

    def parse_descriptors_block(self):
        self.offset += 18 # unknown
        brushes = self.parse_map().get("brush")

        # After parsing descriptors, index the brushes that have sample data
        for brush in brushes:
            sample_id = brush["brush"].get("sampledData")

            if sample_id:
                self.brush_properties[sample_id] = brush

    def parse_one_sample(self, sample_length):
        """Parse one sample in a sample block"""

        start_offset = self.offset
        brush_id = self.parse_id_string()

        if self.major_version == 6 and self.minor_version == 1:
            self.offset += 10 # unknown
            sample_image = self.process_sample_image(sample_length - (start_offset - self.offset))
        else:
            self.unpack('>H') # length to end of block
            self.unpack('>H') # unknown
            sample_image = self.parse_virtual_memory_array_list()

        if sample_image is not None:
            self.brush_mats.append(sample_image)
            self.sample_ids.append(brush_id)

    def parse_virtual_memory_array_list(self):
        """Parse a multi-channel list of images"""

        assert self.unpack('>I') == 3, "expected sample version 3" # version
        self.offset += 4 # length to end of block
        self.offset += 16 # bounds
        num_channels = self.unpack('>I')

        for i in range(num_channels):
            is_written = self.unpack('>I')
            if not is_written:
                continue

            length = self.unpack('>I')
            if not length:
                continue

            self.offset += 4 # depth
            sample_image = self.process_sample_image(length - 4)

        # assume there's only one sample image
        return sample_image

    def process_sample_image(self, byte_length):
        """Extract image matrix of one brush sample"""
        top, left, bottom, right = self.unpack('>IIII')
        depth, compression = self.unpack('>HB')
        
        # Fill pixels in a NumPy array
        img_H, img_W = bottom-top, right-left
        dtype='>u'+str(depth//8)
        
        if compression==0:      # No compression
            pixels_1d = np.frombuffer(self.bytes, dtype=dtype, count=img_H*img_W, offset=self.offset)
            return pixels_1d.reshape((img_H,img_W))
    
        elif compression==1:    # RLE compression
            return rle_decode(self.bytes[self.offset:self.offset+byte_length], img_H, img_W, depth)

    def get_params(self, i):
        sample_id = self.sample_ids[i]
        brush = self.brush_properties.get(sample_id)

        if not brush:
            return (None, {})
        
        name = brush.get("name")
        
        return (name, {})

    def parse_map(self):
        obj = {}

        num_values = self.unpack(">I")
        for i in range(num_values):
            key = self.parse_compact_string()
            value = self.parse_typed_value()
            obj[key] = value

        return obj
    
    def parse_list(self):
        values = []

        num_values = self.unpack(">I")
        for i in range(num_values):
            value = self.parse_typed_value()
            values.append(value)

        return values

    def parse_id_string(self):
        length = self.unpack("b")
        text = self.bytes[self.offset:self.offset + length].decode(encoding='ASCII')
        self.offset += length
        return text

    def parse_compact_string(self):
        length = self.unpack(">I")

        if length == 0:
            # key is a 4-byte constant
            key = self.unpack('>I')
            if key in property_names:
                return property_names[key]
            else:
                return struct.pack('>I', key).decode(encoding='ASCII')
        else:
            text = self.bytes[self.offset:self.offset + length].decode(encoding='ASCII').rstrip("\x00")
            self.offset += length
        return text

    def parse_unicode_string(self):
        char_count = self.unpack('>I')
        length = char_count * 2

        text = self.bytes[self.offset:self.offset + length].decode(encoding='UTF-16BE').rstrip("\u0000\x00")
        self.offset += length
        return text

    def parse_typed_value(self):
        desc_type = self.unpack('>I')

        parser = self.desc_parsers.get(desc_type)
        if parser:
            return parser()
        else:
            raise NotImplementedError("offset " + hex(self.offset) + ": no parser for desc type: " +
                                      struct.pack('>I', desc_type).decode('ASCII'))

    def parse_float(self):
        unit_type = self.unpack('>I') # unit type
        value = self.unpack('>d')
        return UnitFloat(unit_type, value)

    def parse_bool(self):
        return self.unpack('?')
    
    def parse_int(self):
        return self.unpack('>i')
    
    def parse_double(self):
        return self.unpack('>d')
    
    def parse_enum(self):
        self.parse_compact_string() # type
        return self.parse_compact_string() # value

    def parse_descriptor(self):
        self.parse_unicode_string() # seems to be empty
        self.parse_compact_string() # class id
        return self.parse_map()

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
 