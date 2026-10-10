"""Real export matrix, optimizer/comments, alpha modes, batch planning and settings."""
import tempfile,threading
from pathlib import Path
from PIL import Image,ImageChops
from formats import Options,FORMATS,load_image,parse_blp,parse_dds,get_comment,transform_alpha
from operations import convert,optimize,save_comment,folder_jobs
from preferences import Preferences

def main():
    with tempfile.TemporaryDirectory(prefix='blp-studio-formats-') as tmp:
        root=Path(tmp);src=root/'source.png';image=Image.new('RGBA',(32,16))
        for y in range(16):
            for x in range(32):image.putpixel((x,y),(x*8,y*16,(x+y)*5,x*8))
        image.save(src)
        for fmt,ext in FORMATS.items():
            options=Options(format=fmt,mipmaps=3,compress_palette=True)
            output=root/(fmt.replace(' ','-')+ext);report=convert(src,output,options)
            decoded=load_image(output);assert decoded.size==image.size
            if fmt.startswith('BLP'):assert report['mipmaps']==3
            if fmt in ('PNG','BLP1 Paletted','BLP2 Paletted'):assert decoded.getchannel('A').tobytes()==image.getchannel('A').tobytes()
            if fmt.startswith('DDS'):
                assert parse_dds(output.read_bytes())['mipmaps']==3
                for level in range(3):assert load_image(output,level).size==(32>>level,16>>level)
            if fmt=='BMP':assert decoded.tobytes()==image.tobytes()
            print('PASS',fmt)
        removed=root/'removed.png';convert(src,removed,Options(format='PNG',alpha='Remove'))
        with Image.open(removed) as decoded:assert decoded.mode=='RGB'
        for fmt in ('BLP1 Paletted','BLP2 Paletted','BLP2 DXT3','TGA Paletted','DDS DXT5'):
            output=root/('dither-'+fmt.replace(' ','-')+FORMATS[fmt]);convert(src,output,Options(format=fmt,dither=True,mipmaps=2))
            assert load_image(output).size==image.size
        for name in ('None','Sub','Up','Average','Paeth','Adaptive'):
            output=root/(name+'.png');convert(src,output,Options(format='PNG',png_filter=name))
            assert load_image(output).tobytes()==image.tobytes()
        for progressive in (False,True):
            for merge in (False,True):convert(src,root/f'jpeg-{progressive}-{merge}.blp',Options(format='BLP1 JPEG',progressive=progressive,merge_headers=merge))
        for top in (False,True):
            for rle in (False,True):
                for cross in (False,True):
                    output=root/f'tga-{top}-{rle}-{cross}.tga';convert(src,output,Options(format='TGA True Color',tga_top_left=top,tga_rle=rle,tga_cross_lines=cross))
                    assert load_image(output).tobytes()==image.tobytes()
        original=root/'BLP1-Paletted.blp';commented=root/'commented.blp';save_comment(original,commented,'Test comment')
        assert commented.stat().st_size==original.stat().st_size and get_comment(commented.read_bytes())=='Test comment'
        optimized=root/'optimized.blp';padded=root/'padded.blp';padded.write_bytes(commented.read_bytes()+bytes(200))
        report=optimize(padded,optimized);assert report['saved_bytes']>=200
        assert get_comment(optimized.read_bytes())=='Test comment'
        inputs=root/'input';(inputs/'child').mkdir(parents=True);image.save(inputs/'child/sample.png')
        jobs=folder_jobs(inputs,root/'output','BLP2 DXT5');assert jobs[0][1]==root/'output/child/sample.blp'
        settings=root/'preferences.json';prefs=Preferences(settings);prefs.remember(src);assert Preferences(settings).folder()==str(root)
        assert transform_alpha(image,'Opaque').getchannel('A').getextrema()==(255,255)
        assert transform_alpha(image,'Transparent border').getpixel((0,0))[3]==0
        cancelled=threading.Event();cancelled.set()
        try:convert(src,root/'cancelled.blp',Options(),cancelled)
        except InterruptedError:pass
        else:raise AssertionError('Cancellation ignored')
        assert not (root/'cancelled.blp').exists()
        print('PASS: all formats, PNG filters, JPEG header/progressive options, TGA packet/origin options, lossless optimize/comments, recursive batches, folder persistence and cancellation.')

if __name__=='__main__':main()
