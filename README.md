# Import Paint Brush: Blender Add-on

This is an add-on that converts brush assets of several popular painting software to Blender ones.

- Supported brush formats: `.abr`, `.gbr`, `.brushset`, `.sut`
- Supported Blender modes: `Texture Paint` / `Sculpt` / `Vertex Paint` / `Grease Pencil`

## Installation

The add-on works with Blender 3.3 ~ 5.0:

1. Download the archive file from the GitHub Release page. Do not unzip it.
2. In Blender, open `[Edit]->[Preferences]->[Add-ons]` and click the Install button to load the archive. Enable the installed add-on.

## Usage

### Demo Video
https://youtu.be/STM5eU0PRvo

### Import Brush Files

The import operator is available in the menu `[File]->[Import]`. Multiple brush files can be selected at once.

<img src="docs/import_menu.png" height=300>

Please make sure to select the Blender mode where the brush will be used. The imported brush will be displayed in the selected mode only.

### Modify Brush Textures

It is possible that some brushes are not fully compatible with Blender, and their textures may not fit well. In this case, the add-on also provides with some image utilities to modulate the color/alpha channels of imported textures. These utilities are available as a menu in the brush tool settings: `[Tool]->[Brush Settings]->[Texture]`.

<img src="docs/util_menu.png" height=300>

### Animated Texture

Some brush formats such as `.gih` and `.sut` allow a single brush to have multiple texture images, which is not natively supported by Blender. However, the [Animated Texture Brush](https://extensions.blender.org/add-ons/animated-brush/) add-on makes this possible by loading multiple textures as an image sequence.

By default, this add-on splits a multi-texture brush into individual ones. There is also an option `Import Brush as Image Sequence` that makes the brush compatible with Animated Texture Brush.

### Tips

- Blender stores brushes in the current `.blend` file. To reuse the converted brushes in other files, please save the file to your [asset library](https://docs.blender.org/manual/en/latest/files/asset_libraries/introduction.html#what-is-an-asset-library).
- This add-on can only convert brush files that contain texture images. Some brushes, which usually have a very small file size, only store parameters and no images. These brushes cannot be imported.
- Please ensure that you comply with the copyright and licensing terms of the original brush assets. This tool only provides format conversion and does not grant you any additional rights to use or redistribute the converted brushes.

## Credits

The parsing of brush formats is learned from the following documents/projects:

- [Adobe Photoshop File Format Specification](https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/)
- [GIMP Source Code](https://github.com/GNOME/gimp/)
- ["Just Solve the File Format Problem" Wiki](http://fileformats.archiveteam.org/wiki/Photoshop_brush)
- [Krita Wiki](https://community.kde.org/Krita/Photoshop_Mapping_Table)
- [Brush-viewer by jlai](https://github.com/jlai/brush-viewer)
