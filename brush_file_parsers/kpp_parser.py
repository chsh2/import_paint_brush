import struct
import numpy as np

class KppParser:
    """
    Parse Krita KPP brush presets. Currently with the following limitations:
      - Supports only the Pixel Engine ("paintbrush")
      - Focuses on the new format introduced in Krita 5. Not fully tested with the older formats
    """

    def __init__(self, bytes, presets_dir="/tmp"):
        self.bytes = bytes
        self.dir = presets_dir
        self.brush_mats = []
        self.is_tex_grain = []
        self.params = {}                      # One KPP only contains one config file

        self.is_valid_png = True
        if bytes[:8] != b"\x89PNG\r\n\x1a\n":
            self.is_valid_png = False
            return
        self.offset = 8

        # Parse outer PNG structure
        self.png_chunks = []
        while self.offset < len(self.bytes):
            header = bytes[self.offset:self.offset+8]
            if len(header) < 8:
                break
            self.offset += 8
            length, chunk_type = struct.unpack(">I4s", header)
            if length < 1:
                break
            self.png_chunks.append((chunk_type, bytes[self.offset:self.offset+length]))
            self.offset += length + 4
        self.xml = None

    def check(self):
        """Check if a valid XML exists in PNG metadata"""
        if not self.is_valid_png:
            return False

        import zlib
        import xml.etree.ElementTree as ET
        for chunk_type, data in self.png_chunks:
            if chunk_type not in (b"zTXt", b"iTXt", b"tEXt"):
                continue

            xml_str = ""
            null_pos = data.index(b"\x00")
            if chunk_type == b"tEXt":
                xml_str = data[null_pos + 1 :].decode("utf-8", errors="replace")

            if chunk_type == b"zTXt":
                compressed = data[null_pos + 2 :]
                xml_str = zlib.decompress(compressed).decode("utf-8", errors="replace")

            if chunk_type == b"iTXt":
                rest = data[null_pos + 1 :]
                if len(rest) < 2:
                    continue
                compression_flag = rest[0]
                pos = 2
                # Skip language (null-terminated)
                while pos < len(rest) and rest[pos] != 0:
                    pos += 1
                pos += 1
                # Skip translated keyword (null-terminated)
                while pos < len(rest) and rest[pos] != 0:
                    pos += 1
                pos += 2
                if pos >= len(rest):
                    continue
                if compression_flag:
                    xml_str = zlib.decompress(rest[pos:]).decode("utf-8", errors="replace")
                else:
                    xml_str = rest[pos:].decode("utf-8", errors="replace")

            try:
                root = ET.fromstring(xml_str)
            except ET.ParseError:
                continue

            # Accept only supported Brush Engines
            paintopid = root.get("paintopid")
            if paintopid == 'paintbrush':
                self.xml = root
                break

        return self.xml is not None

    def parse(self):
        if self.xml is None:
            if not self.check():
                return

        import os
        import pathlib
        import base64
        import xml.etree.ElementTree as ET

        self.params['KPP_BRUSH_NAME'] = self.xml.get('name')

        # Find resources; unarchive embedded data to temporary files if not found
        for resource in self.xml.findall('.//resource'):
            subdir = resource.get('type')
            filename = resource.get('filename')
            search_path = os.path.join(self.dir, "..", subdir, filename)

            # Reject suspicious paths
            expected_parent = pathlib.Path(self.dir).parent.resolve()
            if not pathlib.Path(search_path).resolve().is_relative_to(expected_parent):
                continue

            # TODO: Consider verifying md5sum
            if not os.path.exists(search_path):
                b64_data = resource.text.strip() if resource.text else ''
                if filename and b64_data:
                    binary_data = base64.b64decode(b64_data)
                    pathlib.Path(os.path.dirname(search_path)).mkdir(parents=True, exist_ok=True)
                    with open(search_path, 'wb') as f:
                        f.write(binary_data)

        # Get brush tip and all other parameters
        nested_params = {"brush_definition"}
        for param in self.xml.findall('param'):
            name = param.get("name")
            text_value = param.text.strip() if param.text else ''
            if name in nested_params:
                try:
                    inner_root = ET.fromstring(text_value)
                    attributes = dict(inner_root.attrib)
                    for key in attributes:
                        self.params[f"{name}/{key}"] = attributes[key]
                except ET.ParseError:
                    self.params[name] = text_value
            else:
                self.params[name] = text_value

        # Load brush tip and texture images
        has_tip, has_tex = False, False
        tip_file_name = self.params.get("brush_definition/filename", None)
        tex_file_name = self.params.get("Texture/Pattern/PatternFileName", None)
        if tip_file_name:
            tip_path = os.path.join(self.dir, "../brushes", tip_file_name)
            if os.path.exists(tip_path):
                tip_mats = self.get_resource_img_mats(tip_path)
                has_tip = len(tip_mats) > 0

        if tex_file_name:
            tex_path = os.path.join(self.dir, "../patterns", tex_file_name)
            if os.path.exists(tex_path):
                tex_mats = self.get_resource_img_mats(tex_path)
                has_tex = len(tex_mats) > 0

        if has_tip:
            self.brush_mats += tip_mats
            self.is_tex_grain += [False for _ in tip_mats]
        if has_tex:
            self.brush_mats += tex_mats
            self.is_tex_grain += [True for _ in tex_mats]

        # Some parameter conversions are based on the actual image size
        if len(self.brush_mats) > 0:
            self.params['KPP_BRUSH_SIZE'] = min(self.brush_mats[0].shape[0], self.brush_mats[0].shape[1])

    def get_resource_img_mats(self, filepath):
        """Resources may be in various formats -- call different parsers to get the image matrices"""
        if filepath.lower().endswith('.abr'):
            from .abr_parser import Abr1Parser, Abr6Parser
            with open(filepath, 'rb') as fd:
                bytes = fd.read()
                major_version = struct.unpack_from('>H',bytes)[0]
                if major_version > 5:
                    parser = Abr6Parser(bytes)
                else:
                    parser = Abr1Parser(bytes)
                if not parser.check():
                    return []
                parser.parse()
                return parser.brush_mats

        elif filepath.lower().endswith('.gbr'):
            from .gbr_parser import GbrParser
            with open(filepath, 'rb') as fd:
                parser = GbrParser(fd.read())
                if not parser.check():
                    return []
                parser.parse()
                return parser.brush_mats

        elif filepath.lower().endswith('.gih'):
            from .gbr_parser import GihParser
            with open(filepath, 'rb') as fd:
                parser = GihParser(fd.read())
                if not parser.check():
                    return []
                parser.parse()
                return parser.brush_mats

        elif filepath.lower().endswith('.png') or filepath.lower().endswith('.jpg') or filepath.lower().endswith('.jpeg') or filepath.lower().endswith('.bmp'):
            try:
                import bpy
                import bpy_extras.image_utils
            except ImportError: # For testing environment
                return []
            img_obj = bpy_extras.image_utils.load_image(filepath, check_existing=True)
            img_W = img_obj.size[0]
            img_H = img_obj.size[1]
            img_mat = np.array(img_obj.pixels).reshape(img_H,img_W, img_obj.channels)
            img_mat = 255 - np.flipud(img_mat[:,:,0]) * 255
            bpy.data.images.remove(img_obj)
            return [img_mat]

        return []  # SVG and other formats are not supported yet

    def get_params(self, i):
        """Return the brush name and parameters. Ignore slot number since there is only one config"""
        return self.params['KPP_BRUSH_NAME'], self.params
