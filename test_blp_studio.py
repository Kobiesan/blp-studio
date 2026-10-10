"""Integration tests of the independent codec, no external executable or GUI mocks."""
import tempfile,struct
from pathlib import Path
from PIL import Image,ImageChops
from blp_studio import convert,inspect_blp,decode_mip
from viewer import display_scale,mip_labels,checker_tiles

def main():
    assert display_scale((64,64),(600,400),'25%')==0.25
    assert display_scale((4096,4096),(600,400),'1%')==0.01
    assert 0<display_scale((4096,2048),(800,400),'Fit')<0.2
    assert display_scale((64,64),(600,400),'1600%')==16
    assert mip_labels({'width':64,'height':32,'mipmaps':7})[-1]=='6: 1 × 1'
    for scale in (0.5,1,1.5,2,4,8):
        width=round(64*scale);rect=(7,9,width,width)
        for bounds,color in checker_tiles(rect,(640,640)):
            assert 7<=bounds[0]<=bounds[2]<7+width and 9<=bounds[1]<=bounds[3]<9+width
    with tempfile.TemporaryDirectory(prefix='blp-studio-test-') as tmp:
        root=Path(tmp);source=root/'source.png'
        image=Image.new('RGBA',(64,64),(176,74,38,255))
        for xy in [(0,0),(63,0),(0,63),(63,63)]:image.putpixel(xy,(0,0,0,0))
        image.save(source)
        original_bytes=source.read_bytes()
        encoded=root/'output.blp';report=convert(source,encoded)
        assert report['source']=='source.png' and report['destination']=='output.blp'
        assert report['mipmaps']==7 and report['maximum_alpha_error']==0
        for level in range(7):assert decode_mip(encoded,level).size==(64>>level,64>>level)
        before=encoded.read_bytes()
        try:convert(source,encoded)
        except FileExistsError:pass
        else:raise AssertionError('Existing output was overwritten')
        assert encoded.read_bytes()==before
        decoded=root/'roundtrip.png';convert(encoded,decoded)
        expected=Image.open(encoded).convert('RGBA');actual=Image.open(decoded).convert('RGBA')
        difference=ImageChops.difference(expected,actual).getextrema()
        # Pillow's legacy BLP plugin and its DDS BCn decoder expand RGB565
        # differently. Alpha must match; endpoint rounding stays within 8/255.
        assert difference[3]==(0,0) and all(bounds[1]<=8 for bounds in difference[:3])
        gradient=Image.new('RGBA',(16,8))
        for y in range(8):
            for x in range(16):gradient.putpixel((x,y),(x*17,y*32,(x+y)*10,(x*13+y*7)%256))
        gradient.save(root/'gradient.png')
        gradient_report=convert(root/'gradient.png',root/'gradient.blp')
        assert gradient_report['maximum_alpha_error']<=8 and gradient_report['mipmaps']==5
        assert decode_mip(root/'gradient.blp',4).size==(1,1)
        malformed=root/'broken.blp';data=bytearray(before);struct.pack_into('<I',data,20,len(data)+1);malformed.write_bytes(data)
        try:inspect_blp(malformed)
        except ValueError:pass
        else:raise AssertionError('Out-of-bounds mip accepted')
        odd=root/'odd.png';Image.new('RGBA',(63,64)).save(odd)
        convert(odd,root/'odd.blp')
        assert decode_mip(root/'odd.blp',0).size==(63,64)
        try:convert(root/'missing.png',root/'missing.blp')
        except FileNotFoundError:pass
        else:raise AssertionError('Missing input accepted')
        assert source.read_bytes()==original_bytes
        print('PASS: built-in PNG->BLP->PNG, alpha/corners, seven decoded mips, overwrite refusal, malformed mip rejection, dimensions and missing-input errors.')

if __name__=='__main__':main()
