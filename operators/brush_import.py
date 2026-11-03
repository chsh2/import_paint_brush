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

def set_icon_overlay_text(img):
    """Add a letter 'A' at the icon bottom left corner for an animated brush"""
    BLACK_INDICES = [4886, 4887, 4888, 4889, 4890, 4921, 4922, 4923, 4924, 4925, 5143, 5144, 5145, 5146, 5147, 5176, 5177, 5178, 5179, 5180, 5181, 5399, 5400, 5401, 5402, 5403, 5432, 5433, 5434, 5435, 5436, 5656, 5657, 5658, 5659, 5660, 5688, 5689, 5690, 5691, 5692, 5912, 5913, 5914, 5915, 5916, 5943, 5944, 5945, 5946, 5947, 6168, 6169, 6170, 6171, 6172, 6199, 6200, 6201, 6202, 6203, 6425, 6426, 6427, 6428, 6429, 6455, 6456, 6457, 6458, 6459, 6681, 6682, 6683, 6684, 6685, 6710, 6711, 6712, 6713, 6714, 6938, 6939, 6940, 6941, 6942, 6966, 6967, 6968, 6969, 6970, 7194, 7195, 7196, 7197, 7198, 7221, 7222, 7223, 7224, 7225, 7226, 7450, 7451, 7452, 7453, 7454, 7477, 7478, 7479, 7480, 7481, 7707, 7708, 7709, 7710, 7711, 7733, 7734, 7735, 7736, 7737, 7963, 7964, 7965, 7966, 7967, 7988, 7989, 7990, 7991, 7992, 8220, 8221, 8222, 8223, 8224, 8244, 8245, 8246, 8247, 8248, 8476, 8477, 8478, 8479, 8480, 8481, 8482, 8483, 8484, 8485, 8486, 8487, 8488, 8489, 8490, 8491, 8492, 8493, 8494, 8495, 8496, 8497, 8498, 8499, 8500, 8501, 8502, 8503, 8504, 8732, 8733, 8734, 8735, 8736, 8737, 8738, 8739, 8740, 8741, 8742, 8743, 8744, 8745, 8746, 8747, 8748, 8749, 8750, 8751, 8752, 8753, 8754, 8755, 8756, 8757, 8758, 8759, 8989, 8990, 8991, 8992, 8993, 8994, 8995, 8996, 8997, 8998, 8999, 9000, 9001, 9002, 9003, 9004, 9005, 9006, 9007, 9008, 9009, 9010, 9011, 9012, 9013, 9014, 9015, 9245, 9246, 9247, 9248, 9249, 9250, 9251, 9252, 9253, 9254, 9255, 9256, 9257, 9258, 9259, 9260, 9261, 9262, 9263, 9264, 9265, 9266, 9267, 9268, 9269, 9270, 9502, 9503, 9504, 9505, 9506, 9507, 9508, 9509, 9510, 9511, 9512, 9513, 9514, 9515, 9516, 9517, 9518, 9519, 9520, 9521, 9522, 9523, 9524, 9525, 9526, 9758, 9759, 9760, 9761, 9762, 9778, 9779, 9780, 9781, 9782, 10014, 10015, 10016, 10017, 10018, 10033, 10034, 10035, 10036, 10037, 10271, 10272, 10273, 10274, 10275, 10289, 10290, 10291, 10292, 10293, 10527, 10528, 10529, 10530, 10531, 10544, 10545, 10546, 10547, 10548, 10784, 10785, 10786, 10787, 10800, 10801, 10802, 10803, 10804, 11040, 11041, 11042, 11043, 11044, 11056, 11057, 11058, 11059, 11060, 11296, 11297, 11298, 11299, 11300, 11311, 11312, 11313, 11314, 11315, 11553, 11554, 11555, 11556, 11557, 11567, 11568, 11569, 11570, 11571, 11809, 11810, 11811, 11812, 11813, 11823, 11824, 11825, 11826, 12065, 12066, 12067, 12068, 12069, 12078, 12079, 12080, 12081, 12082, 12322, 12323, 12324, 12325, 12326, 12334, 12335, 12336, 12337, 12338, 12578, 12579, 12580, 12581, 12582, 12590, 12591, 12592, 12593, 12835, 12836, 12837, 12838, 12845, 12846, 12847, 12848, 12849, 13091, 13092, 13093, 13094, 13095, 13101, 13102, 13103, 13104, 13105, 13347, 13348, 13349, 13350, 13351, 13356, 13357, 13358, 13359, 13360, 13604, 13605, 13606, 13607, 13612, 13613, 13614, 13615, 13616, 13860, 13861, 13862, 13863, 13864, 13868, 13869, 13870, 13871, 14117, 14118, 14119, 14120, 14123, 14124, 14125, 14126, 14127, 14373, 14374, 14375, 14376, 14379, 14380, 14381, 14382, 14383, 14629, 14630, 14631, 14632, 14633, 14635, 14636, 14637, 14638, 14886, 14887, 14888, 14889, 14890, 14891, 14892, 14893, 14894, 15142, 15143, 15144, 15145, 15146, 15147, 15148, 15149, 15399, 15400, 15401, 15402, 15403, 15404, 15405, 15655, 15656, 15657, 15658, 15659, 15660, 15661, 15911, 15912, 15913, 15914, 15915, 15916, 16168, 16169, 16170, 16171, 16172]
    WHITE_INDICES = [3342, 3343, 3344, 3345, 3346, 3347, 3348, 3349, 3350, 3351, 3352, 3353, 3354, 3355, 3356, 3357, 3358, 3381, 3382, 3383, 3384, 3385, 3386, 3387, 3388, 3389, 3390, 3391, 3392, 3393, 3394, 3395, 3396, 3397, 3598, 3599, 3600, 3601, 3602, 3603, 3604, 3605, 3606, 3607, 3608, 3609, 3610, 3611, 3612, 3613, 3614, 3615, 3637, 3638, 3639, 3640, 3641, 3642, 3643, 3644, 3645, 3646, 3647, 3648, 3649, 3650, 3651, 3652, 3653, 3855, 3856, 3857, 3858, 3859, 3860, 3861, 3862, 3863, 3864, 3865, 3866, 3867, 3868, 3869, 3870, 3871, 3892, 3893, 3894, 3895, 3896, 3897, 3898, 3899, 3900, 3901, 3902, 3903, 3904, 3905, 3906, 3907, 3908, 3909, 4111, 4112, 4113, 4114, 4115, 4116, 4117, 4118, 4119, 4120, 4121, 4122, 4123, 4124, 4125, 4126, 4127, 4148, 4149, 4150, 4151, 4152, 4153, 4154, 4155, 4156, 4157, 4158, 4159, 4160, 4161, 4162, 4163, 4164, 4368, 4369, 4370, 4371, 4372, 4373, 4374, 4375, 4376, 4377, 4378, 4379, 4380, 4381, 4382, 4383, 4384, 4404, 4405, 4406, 4407, 4408, 4409, 4410, 4411, 4412, 4413, 4414, 4415, 4416, 4417, 4418, 4419, 4420, 4624, 4625, 4626, 4627, 4628, 4629, 4630, 4631, 4632, 4633, 4634, 4635, 4636, 4637, 4638, 4639, 4640, 4659, 4660, 4661, 4662, 4663, 4664, 4665, 4666, 4667, 4668, 4669, 4670, 4671, 4672, 4673, 4674, 4675, 4880, 4881, 4882, 4883, 4884, 4885, 4891, 4892, 4893, 4894, 4895, 4896, 4897, 4915, 4916, 4917, 4918, 4919, 4920, 4926, 4927, 4928, 4929, 4930, 4931, 5137, 5138, 5139, 5140, 5141, 5142, 5148, 5149, 5150, 5151, 5152, 5153, 5170, 5171, 5172, 5173, 5174, 5175, 5182, 5183, 5184, 5185, 5186, 5187, 5393, 5394, 5395, 5396, 5397, 5398, 5404, 5405, 5406, 5407, 5408, 5409, 5426, 5427, 5428, 5429, 5430, 5431, 5437, 5438, 5439, 5440, 5441, 5442, 5650, 5651, 5652, 5653, 5654, 5655, 5661, 5662, 5663, 5664, 5665, 5666, 5682, 5683, 5684, 5685, 5686, 5687, 5693, 5694, 5695, 5696, 5697, 5698, 5906, 5907, 5908, 5909, 5910, 5911, 5917, 5918, 5919, 5920, 5921, 5922, 5937, 5938, 5939, 5940, 5941, 5942, 5948, 5949, 5950, 5951, 5952, 5953, 6162, 6163, 6164, 6165, 6166, 6167, 6173, 6174, 6175, 6176, 6177, 6178, 6179, 6193, 6194, 6195, 6196, 6197, 6198, 6204, 6205, 6206, 6207, 6208, 6209, 6419, 6420, 6421, 6422, 6423, 6424, 6430, 6431, 6432, 6433, 6434, 6435, 6448, 6449, 6450, 6451, 6452, 6453, 6454, 6460, 6461, 6462, 6463, 6464, 6465, 6675, 6676, 6677, 6678, 6679, 6680, 6686, 6687, 6688, 6689, 6690, 6691, 6704, 6705, 6706, 6707, 6708, 6709, 6715, 6716, 6717, 6718, 6719, 6720, 6932, 6933, 6934, 6935, 6936, 6937, 6943, 6944, 6945, 6946, 6947, 6948, 6960, 6961, 6962, 6963, 6964, 6965, 6971, 6972, 6973, 6974, 6975, 6976, 7188, 7189, 7190, 7191, 7192, 7193, 7199, 7200, 7201, 7202, 7203, 7204, 7205, 7206, 7207, 7208, 7209, 7210, 7211, 7212, 7213, 7214, 7215, 7216, 7217, 7218, 7219, 7220, 7227, 7228, 7229, 7230, 7231, 7232, 7444, 7445, 7446, 7447, 7448, 7449, 7455, 7456, 7457, 7458, 7459, 7460, 7461, 7462, 7463, 7464, 7465, 7466, 7467, 7468, 7469, 7470, 7471, 7472, 7473, 7474, 7475, 7476, 7482, 7483, 7484, 7485, 7486, 7487, 7701, 7702, 7703, 7704, 7705, 7706, 7712, 7713, 7714, 7715, 7716, 7717, 7718, 7719, 7720, 7721, 7722, 7723, 7724, 7725, 7726, 7727, 7728, 7729, 7730, 7731, 7732, 7738, 7739, 7740, 7741, 7742, 7743, 7957, 7958, 7959, 7960, 7961, 7962, 7968, 7969, 7970, 7971, 7972, 7973, 7974, 7975, 7976, 7977, 7978, 7979, 7980, 7981, 7982, 7983, 7984, 7985, 7986, 7987, 7993, 7994, 7995, 7996, 7997, 7998, 8214, 8215, 8216, 8217, 8218, 8219, 8225, 8226, 8227, 8228, 8229, 8230, 8231, 8232, 8233, 8234, 8235, 8236, 8237, 8238, 8239, 8240, 8241, 8242, 8243, 8249, 8250, 8251, 8252, 8253, 8254, 8470, 8471, 8472, 8473, 8474, 8475, 8505, 8506, 8507, 8508, 8509, 8510, 8726, 8727, 8728, 8729, 8730, 8731, 8760, 8761, 8762, 8763, 8764, 8765, 8983, 8984, 8985, 8986, 8987, 8988, 9016, 9017, 9018, 9019, 9020, 9021, 9239, 9240, 9241, 9242, 9243, 9244, 9271, 9272, 9273, 9274, 9275, 9276, 9496, 9497, 9498, 9499, 9500, 9501, 9527, 9528, 9529, 9530, 9531, 9532, 9752, 9753, 9754, 9755, 9756, 9757, 9763, 9764, 9765, 9766, 9767, 9768, 9769, 9770, 9771, 9772, 9773, 9774, 9775, 9776, 9777, 9783, 9784, 9785, 9786, 9787, 9788, 10008, 10009, 10010, 10011, 10012, 10013, 10019, 10020, 10021, 10022, 10023, 10024, 10025, 10026, 10027, 10028, 10029, 10030, 10031, 10032, 10038, 10039, 10040, 10041, 10042, 10043, 10265, 10266, 10267, 10268, 10269, 10270, 10276, 10277, 10278, 10279, 10280, 10281, 10282, 10283, 10284, 10285, 10286, 10287, 10288, 10294, 10295, 10296, 10297, 10298, 10299, 10521, 10522, 10523, 10524, 10525, 10526, 10532, 10533, 10534, 10535, 10536, 10537, 10538, 10539, 10540, 10541, 10542, 10543, 10549, 10550, 10551, 10552, 10553, 10554, 10778, 10779, 10780, 10781, 10782, 10783, 10788, 10789, 10790, 10791, 10792, 10793, 10794, 10795, 10796, 10797, 10798, 10799, 10805, 10806, 10807, 10808, 10809, 10810, 11034, 11035, 11036, 11037, 11038, 11039, 11045, 11046, 11047, 11048, 11049, 11050, 11051, 11052, 11053, 11054, 11055, 11061, 11062, 11063, 11064, 11065, 11066, 11290, 11291, 11292, 11293, 11294, 11295, 11301, 11302, 11303, 11304, 11305, 11306, 11307, 11308, 11309, 11310, 11316, 11317, 11318, 11319, 11320, 11321, 11547, 11548, 11549, 11550, 11551, 11552, 11558, 11559, 11560, 11561, 11562, 11563, 11564, 11565, 11566, 11572, 11573, 11574, 11575, 11576, 11577, 11803, 11804, 11805, 11806, 11807, 11808, 11814, 11815, 11816, 11817, 11818, 11819, 11820, 11821, 11822, 11827, 11828, 11829, 11830, 11831, 11832, 12059, 12060, 12061, 12062, 12063, 12064, 12070, 12071, 12072, 12073, 12074, 12075, 12076, 12077, 12083, 12084, 12085, 12086, 12087, 12088, 12316, 12317, 12318, 12319, 12320, 12321, 12327, 12328, 12329, 12330, 12331, 12332, 12333, 12339, 12340, 12341, 12342, 12343, 12344, 12572, 12573, 12574, 12575, 12576, 12577, 12583, 12584, 12585, 12586, 12587, 12588, 12589, 12594, 12595, 12596, 12597, 12598, 12599, 12829, 12830, 12831, 12832, 12833, 12834, 12839, 12840, 12841, 12842, 12843, 12844, 12850, 12851, 12852, 12853, 12854, 12855, 13085, 13086, 13087, 13088, 13089, 13090, 13096, 13097, 13098, 13099, 13100, 13106, 13107, 13108, 13109, 13110, 13111, 13341, 13342, 13343, 13344, 13345, 13346, 13352, 13353, 13354, 13355, 13361, 13362, 13363, 13364, 13365, 13366, 13598, 13599, 13600, 13601, 13602, 13603, 13608, 13609, 13610, 13611, 13617, 13618, 13619, 13620, 13621, 13622, 13854, 13855, 13856, 13857, 13858, 13859, 13865, 13866, 13867, 13872, 13873, 13874, 13875, 13876, 13877, 14111, 14112, 14113, 14114, 14115, 14116, 14121, 14122, 14128, 14129, 14130, 14131, 14132, 14133, 14367, 14368, 14369, 14370, 14371, 14372, 14377, 14378, 14384, 14385, 14386, 14387, 14388, 14389, 14623, 14624, 14625, 14626, 14627, 14628, 14634, 14639, 14640, 14641, 14642, 14643, 14644, 14880, 14881, 14882, 14883, 14884, 14885, 14895, 14896, 14897, 14898, 14899, 14900, 15136, 15137, 15138, 15139, 15140, 15141, 15150, 15151, 15152, 15153, 15154, 15155, 15393, 15394, 15395, 15396, 15397, 15398, 15406, 15407, 15408, 15409, 15410, 15411, 15649, 15650, 15651, 15652, 15653, 15654, 15662, 15663, 15664, 15665, 15666, 15667, 15905, 15906, 15907, 15908, 15909, 15910, 15917, 15918, 15919, 15920, 15921, 15922, 16162, 16163, 16164, 16165, 16166, 16167, 16173, 16174, 16175, 16176, 16177, 16178, 16418, 16419, 16420, 16421, 16422, 16423, 16424, 16425, 16426, 16427, 16428, 16429, 16430, 16431, 16432, 16433, 16675, 16676, 16677, 16678, 16679, 16680, 16681, 16682, 16683, 16684, 16685, 16686, 16687, 16688, 16689, 16931, 16932, 16933, 16934, 16935, 16936, 16937, 16938, 16939, 16940, 16941, 16942, 16943, 16944, 16945, 17187, 17188, 17189, 17190, 17191, 17192, 17193, 17194, 17195, 17196, 17197, 17198, 17199, 17200, 17444, 17445, 17446, 17447, 17448, 17449, 17450, 17451, 17452, 17453, 17454, 17455, 17456, 17700, 17701, 17702, 17703, 17704, 17705, 17706, 17707, 17708, 17709, 17710, 17711]
    BLACK_INDICES = np.array(BLACK_INDICES, dtype=np.int32)
    WHITE_INDICES = np.array(WHITE_INDICES, dtype=np.int32)
    icon_pixels = np.zeros(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(icon_pixels)
    icon_pixels[BLACK_INDICES*4] = 0.0
    icon_pixels[BLACK_INDICES*4+1] = 0.0
    icon_pixels[BLACK_INDICES*4+2] = 0.0
    icon_pixels[BLACK_INDICES*4+3] = 1.0
    icon_pixels[WHITE_INDICES*4] = 1.0
    icon_pixels[WHITE_INDICES*4+1] = 1.0
    icon_pixels[WHITE_INDICES*4+2] = 1.0
    icon_pixels[WHITE_INDICES*4+3] = 1.0
    img.pixels.foreach_set(icon_pixels)

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
                img_obj.alpha_mode = 'PREMUL'

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
                if self.import_as_sequence:
                    set_icon_overlay_text(icon_obj)
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
                                new_brush.gpencil_settings.pen_strength = orig_params['toolOptions']['Opct'] * 0.01
                            new_brush.strength = orig_params['toolOptions']['Opct'] * 0.01

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
