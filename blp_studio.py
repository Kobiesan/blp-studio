"""BLP Studio: standalone texture viewer and converter."""
import argparse,json
from pathlib import Path
from operations import convert,inspect_blp,decode_mip
from operations import optimize,save_comment
from formats import Options,FORMATS

def run_gui(initial_files=None):
    from viewer import run_gui as show_viewer
    show_viewer(initial_files)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',nargs='?');parser.add_argument('destination',nargs='?')
    parser.add_argument('--inspect',type=Path,nargs='?',const=True)
    parser.add_argument('--format',choices=list(FORMATS))
    parser.add_argument('--mipmaps',type=int,default=0)
    parser.add_argument('--alpha',choices=['Preserve','Opaque','Remove','Auto','Transparent border'],default='Preserve')
    parser.add_argument('--operation',choices=['convert','optimize','comment'],default='convert')
    parser.add_argument('--comment',default='')
    args=parser.parse_args()
    if args.inspect:
        target=args.source if args.inspect is True else args.inspect
        if not target:parser.error('Provide a file to inspect.')
        print(json.dumps(inspect_blp(target),indent=2))
    elif args.source and args.destination:
        if args.operation=='optimize':report=optimize(args.source,args.destination)
        elif args.operation=='comment':report=save_comment(args.source,args.destination,args.comment)
        else:
            default={'.blp':'BLP2 DXT3','.png':'PNG','.jpg':'JPEG','.jpeg':'JPEG','.bmp':'BMP','.tga':'TGA True Color','.dds':'DDS DXT3'}
            report=convert(args.source,args.destination,Options(format=args.format or default.get(Path(args.destination).suffix.lower(),''),mipmaps=args.mipmaps,alpha=args.alpha,comment=args.comment))
        print(json.dumps(report,indent=2))
    elif args.source:run_gui([args.source])
    elif args.destination:parser.error('Provide a source.')
    else:run_gui()
