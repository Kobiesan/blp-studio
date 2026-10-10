import subprocess,tempfile,json,sys
from pathlib import Path
from PIL import Image
from formats import FORMATS,load_image,parse_blp,parse_dds,get_comment

def main():
    executable=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).parent/'BLPStudio.exe'
    with tempfile.TemporaryDirectory(prefix='blp-studio-release-') as tmp:
        folder=Path(tmp);source=folder/'source.png';Image.new('RGBA',(32,32),(155,75,35,170)).save(source)
        def run(*args):
            result=subprocess.run([str(executable),*map(str,args)],capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            assert result.returncode==0,(result.returncode,result.stderr)
        for fmt,ext in FORMATS.items():
            target=folder/(fmt.replace(' ','-')+ext)
            run(source,target,'--format',fmt,'--mipmaps',3)
            assert target.exists() and load_image(target).size==(32,32)
            receipt=json.loads(target.with_name(target.name+'.conversion.json').read_text())
            assert receipt['options']['format']==fmt and receipt['source']=='source.png'
            if fmt.startswith('BLP'):assert parse_blp(target.read_bytes())['mipmaps']==3
            if fmt.startswith('DDS'):assert parse_dds(target.read_bytes())['mipmaps']==3
            print('PASS executable',fmt)
        blp=folder/'BLP1-Paletted.blp';comment=folder/'comment.blp'
        run(blp,comment,'--operation','comment','--comment','Release test')
        assert get_comment(comment.read_bytes())=='Release test'
        run(comment,folder/'optimized.blp','--operation','optimize')
        run(blp,'--inspect')
        print('PASS standalone executable formats, comments, optimizer and inspection')

if __name__=='__main__':main()
