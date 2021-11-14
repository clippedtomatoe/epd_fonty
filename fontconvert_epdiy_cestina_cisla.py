#!python3
import freetype
import zlib
import sys
import re
import math
import argparse
from collections import namedtuple

parser = argparse.ArgumentParser(description="Generate a header file from a font to be used with epdiy.")
parser.add_argument("name", action="store", help="name of the font.")
parser.add_argument("size", type=int, help="font size to use.")
parser.add_argument("fontstack", action="store", nargs='+', help="list of font files, ordered by descending priority.")
parser.add_argument("--compress", dest="compress", action="store_true", help="compress glyph bitmaps.")
parser.add_argument("--additional-intervals", dest="additional_intervals", action="append", help="Additional code point intervals to export as min,max. This argument can be repeated.")
args = parser.parse_args()

GlyphProps = namedtuple("GlyphProps", ["width", "height", "advance_x", "left", "top", "compressed_size", "data_offset", "code_point"])

font_stack = [freetype.Face(f) for f in args.fontstack]
compress = args.compress
size = args.size
font_name = args.name

# inclusive unicode code point intervals
# must not overlap and be in ascending order

# Roboto: https://www.fileformat.info/info/unicode/font/roboto/grid.htm
intervals = [
    #-
    (0x002d, 0x002d),
    #cisla
    (0x0030, 0x0039),
    #zakladni latinka velka
    (0x0041, 0x005a),
    #zakladni latinka mala 
    (0x0061, 0x007a),
    #Á
    (0x00c1, 0x00c1),
    #É
    (0x00c9, 0x00c9),
    #Í
    (0x00cd, 0x00cd),
    #Ó
    (0x00c1, 0x00c1),
    #Ú
    (0x00c1, 0x00c1),
    #Ý
    (0x00c1, 0x00c1),
    #á
    (0x00e1, 0x00e1),
    #é
    (0x00e9, 0x00e9),
    #í
    (0x00ed, 0x00ed),
    #ó
    (0x00f3, 0x00f3),
    #ú
    (0x00fa, 0x00fa),
    #ý
    (0x00fd, 0x00fd),
    #Č
    (0x010c, 0x010c),
    #č
    (0x010d, 0x010d),
    #Ď
    (0x010e, 0x010e),
    #ď
    (0x010f, 0x010f),
    #Ě
    (0x011a, 0x011a),
    #ě
    (0x011b, 0x011b),
    #Ň
    (0x0147, 0x0147),
    #ň
    (0x0148, 0x0148),
    #Ř
    (0x0158, 0x0158),
    #ř
    (0x0159, 0x0159),    
    #Š
    (0x0160, 0x0160),
    #š
    (0x0161, 0x0161),
    #Ť
    (0x0164, 0x0164),
    #ť
    (0x0165, 0x0165),
    #Ů
    (0x016e, 0x016e),
    #ů
    (0x016f, 0x016f),
    #Ž
    (0x017d, 0x017d),
    #ž
    (0x017e, 0x017e)
    
    #dodatek latinky
#    (0x00c0, 0x00ff),
    #rozsireni latinka A
#    (0x0100, 0x017e)
#    (32, 126),
#    (160, 255),
    # punctuation
#    (0x2010, 0x205F),
    # arrows
#    (0x2190, 0x21FF),
    # math
    #(0x2200, 0x22FF),
    # symbols
#    (0x2300, 0x23FF),
    # box drawing
    #(0x2500, 0x259F),
    # geometric shapes
#    (0x25A0, 0x25FF),
    # misc symbols
#    (0x2600, 0x26F0),
#    (0x2700, 0x27BF),
    # powerline symbols
    #(0xE0A0, 0xE0A2),
    #(0xE0B0, 0xE0B3),
    #(0x1F600, 0x1F680),
]

add_ints = []
if args.additional_intervals:
    add_ints = [tuple([int(n, base=0) for n in i.split(",")]) for i in args.additional_intervals]

intervals = sorted(intervals + add_ints)

def norm_floor(val):
    return int(math.floor(val / (1 << 6)))

def norm_ceil(val):
    return int(math.ceil(val / (1 << 6)))

for face in font_stack:
    # shift by 6 bytes, because sizes are given as 6-bit fractions
    # the display has about 150 dpi.
    face.set_char_size(size << 6, size << 6, 150, 150)

def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]

total_size = 0
total_packed = 0
all_glyphs = []

def load_glyph(code_point):
    face_index = 0
    while face_index < len(font_stack):
        face = font_stack[face_index]
        glyph_index = face.get_char_index(code_point)
        if glyph_index > 0:
            face.load_glyph(glyph_index, freetype.FT_LOAD_RENDER)
            return face
            break
        face_index += 1
        print (f"falling back to font {face_index} for {chr(code_point)}.", file=sys.stderr)
    raise ValueError(f"code point {code_point} not found in font stack!")

for i_start, i_end in intervals:
    for code_point in range(i_start, i_end + 1):
        face = load_glyph(code_point)
        bitmap = face.glyph.bitmap
        pixels = []
        px = 0
        for i, v in enumerate(bitmap.buffer):
            y = i / bitmap.width
            x = i % bitmap.width
            if x % 2 == 0:
                px = (v >> 4)
            else:
                px = px | (v & 0xF0)
                pixels.append(px);
                px = 0
            # eol
            if x == bitmap.width - 1 and bitmap.width % 2 > 0:
                pixels.append(px)
                px = 0

        packed = bytes(pixels);
        total_packed += len(packed)
        compressed = packed
        if compress:
            compressed = zlib.compress(packed)

        glyph = GlyphProps(
            width = bitmap.width,
            height = bitmap.rows,
            advance_x = norm_floor(face.glyph.advance.x),
            left = face.glyph.bitmap_left,
            top = face.glyph.bitmap_top,
            compressed_size = len(compressed),
            data_offset = total_size,
            code_point = code_point,
        )
        total_size += len(compressed)
        all_glyphs.append((glyph, compressed))

# pipe seems to be a good heuristic for the "real" descender
face = load_glyph(ord('|'))

glyph_data = []
glyph_props = []
for index, glyph in enumerate(all_glyphs):
    props, compressed = glyph
    glyph_data.extend([b for b in compressed])
    glyph_props.append(props)

print("total", total_packed, file=sys.stderr)
print("compressed", total_size, file=sys.stderr)

print("#pragma once")
print("#include \"epd_driver.h\"")
print(f"const uint8_t {font_name}Bitmaps[{len(glyph_data)}] = {{")
for c in chunks(glyph_data, 16):
    print ("    " + " ".join(f"0x{b:02X}," for b in c))
print ("};");

print(f"const EpdGlyph {font_name}Glyphs[] = {{")
for i, g in enumerate(glyph_props):
    print ("    { " + ", ".join([f"{a}" for a in list(g[:-1])]),"},", f"// {chr(g.code_point) if g.code_point != 92 else '<backslash>'}")
print ("};");

print(f"const EpdUnicodeInterval {font_name}Intervals[] = {{")
offset = 0
for i_start, i_end in intervals:
    print (f"    {{ 0x{i_start:X}, 0x{i_end:X}, 0x{offset:X} }},")
    offset += i_end - i_start + 1
print ("};");

print(f"const EpdFont {font_name} = {{")
print(f"    {font_name}Bitmaps,")
print(f"    {font_name}Glyphs,")
print(f"    {font_name}Intervals,")
print(f"    {len(intervals)},")
print(f"    {1 if compress else 0},")
print(f"    {norm_ceil(face.size.height)},")
print(f"    {norm_ceil(face.size.ascender)},")
print(f"    {norm_floor(face.size.descender)},")
print("};")
