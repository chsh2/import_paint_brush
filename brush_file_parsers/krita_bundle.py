import os

class BundleProcessor():
    """
    A Krita bundle file may contain multiple: textures, GIMP brushes and KPP brush presets.
    This processor extracts related files to a temporary location, and return a list of brush files for further parsing
    """
    def __init__(self, filename):
        self.filename = filename
        self.tmp_dir = None

    def unarchive(self, dst_dir):
        """
        Extract all files to a folder, which is usually Blender's temporary directory
        """
        import zipfile
        import uuid

        if not zipfile.is_zipfile(self.filename):
            return False

        bundle_tmp_dir = os.path.join(dst_dir, str(uuid.uuid4()))
        with zipfile.ZipFile(self.filename, 'r') as zip_ref:
            zip_ref.extractall(bundle_tmp_dir)

        self.tmp_dir = bundle_tmp_dir
        return True

    def get_gimp_brush_files(self):
        """
        Krita bundle archive may contain GIMP brushes as textures. This function provides an option to use these brushes directly
        """
        res = []
        if self.tmp_dir is None:
            return res
        brushes_dir = os.path.join(self.tmp_dir, "brushes")
        if not os.path.exists(brushes_dir):
            return res

        files = os.listdir(brushes_dir)
        for f in files:
            file_path = os.path.join(brushes_dir, f)
            if os.path.isfile(file_path) and (file_path.endswith(".gbr") or file_path.endswith(".gih")):
                res.append(file_path)
        return res

    def get_kpp_brush_files(self):
        """
        Get all KPP preset files, while keeping other files because they may be referred by KPP
        """
        res = []
        presets_dir = os.path.join(self.tmp_dir, "paintoppresets")
        if not os.path.exists(presets_dir):
            return res

        files = os.listdir(presets_dir)
        for f in files:
            file_path = os.path.join(presets_dir, f)
            if os.path.isfile(file_path) and file_path.endswith(".kpp"):
                res.append(file_path)
        return res