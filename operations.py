"""Validated, non-destructive conversion, optimization, comments and batches."""
import json,math,threading
from dataclasses import asdict
from pathlib import Path
from PIL import Image,ImageChops
from formats import Options,FORMATS,encode_image,load_image,parse_blp,parse_dds,decode_blp,decode_raster,transform_alpha,optimize_blp,set_comment,get_comment

EXTENSIONS={'.blp','.png','.bmp','.tga','.jpg','.jpeg','.dds'}

def inspect_blp(path):
    info=parse_dds(Path(path).read_bytes()) if Path(path).suffix.lower()=='.dds' else parse_blp(Path(path).read_bytes())
    return {k:v for k,v in info.items() if k not in ('offsets','sizes','base','offset_at')}

def decode_mip(path,level):return load_image(path,level)

def write_new(path,data,report):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as handle:handle.write(data)
    try:
        with path.with_name(path.name+'.conversion.json').open('x',encoding='utf-8') as handle:json.dump(report,handle,indent=2)
    except FileExistsError:pass

def convert(source,destination,options=None,cancel=None,progress=None):
    source,destination=Path(source),Path(destination)
    if destination.exists():raise FileExistsError(f'Output already exists: {destination.name}. Choose a new name.')
    if not source.is_file():raise FileNotFoundError('Source not found.')
    if options is None:
        default={'.blp':'BLP2 DXT3','.png':'PNG','.jpg':'JPEG','.jpeg':'JPEG','.bmp':'BMP','.tga':'TGA True Color','.dds':'DDS DXT3'}
        options=Options(format=default.get(destination.suffix.lower(),''))
    if options.format not in FORMATS:raise ValueError('Unsupported output format.')
    if destination.suffix.lower()!=FORMATS[options.format] and not(options.format=='JPEG' and destination.suffix.lower()=='.jpeg'):
        raise ValueError('Output extension does not match the chosen format.')
    original=load_image(source);data=encode_image(original,options,cancel,progress)
    if cancel and cancel.is_set():raise InterruptedError('Conversion cancelled.')
    if data[:4] in (b'BLP1',b'BLP2'):
        info=parse_blp(data);decoded=decode_blp(data);expected_count=options.mipmaps or int(math.log2(max(original.size)))+1
        expected_count=min(expected_count,int(math.log2(max(original.size)))+1)
        if info['mipmaps']!=expected_count:raise ValueError('Unexpected mip count.')
        for level in range(info['mipmaps']):decode_blp(data,level).load()
    else:
        import io
        decoded=decode_raster(io.BytesIO(data));decoded.load()
        info={'format':options.format,'bytes':len(data),'width':decoded.width,'height':decoded.height}
    if decoded.size!=original.size:raise ValueError('Export changed dimensions.')
    reference=transform_alpha(original,options.alpha)
    error=max(ImageChops.difference(reference.getchannel('A'),decoded.getchannel('A')).getextrema())
    if options.format in ('BLP2 DXT3','DDS DXT3') and error>8:raise ValueError('DXT3 alpha validation failed.')
    if 'Paletted' in options.format and options.format.startswith('BLP') and error!=0:raise ValueError('Palette alpha changed.')
    if options.format=='PNG' and any(bounds!=(0,0) for bounds in ImageChops.difference(reference,decoded).getextrema()):raise ValueError('Lossless PNG validation failed.')
    report={k:v for k,v in info.items() if k not in ('offsets','sizes','base','offset_at')}
    report.update(source=source.name,destination=destination.name,codec='BLP Studio',maximum_alpha_error=error,options=asdict(options))
    write_new(destination,data,report);return report

def optimize(source,destination,compress_palette=True):
    source,destination=Path(source),Path(destination)
    if destination.exists():raise FileExistsError('Choose a new optimizer output name.')
    raw=source.read_bytes();result=optimize_blp(raw,compress_palette);info=parse_blp(raw)
    # Verify each mip remains byte-identical, in addition to decoded pixels.
    new=parse_blp(result)
    for i in range(info['mipmaps']):
        a=raw[info['offsets'][i]:info['offsets'][i]+info['sizes'][i]]
        b=result[new['offsets'][i]:new['offsets'][i]+new['sizes'][i]]
        if a!=b or decode_blp(raw,i).tobytes()!=decode_blp(result,i).tobytes():raise ValueError('Optimizer changed image data.')
    if len(result)>len(raw):result=raw
    report={'source':source.name,'destination':destination.name,'operation':'lossless optimize','before_bytes':len(raw),'after_bytes':len(result),'saved_bytes':len(raw)-len(result)}
    write_new(destination,result,report);return report

def save_comment(source,destination,text):
    raw=Path(source).read_bytes();result=set_comment(raw,text)
    if len(raw)!=len(result):raise ValueError('Header comment changed file size.')
    report={'source':Path(source).name,'destination':Path(destination).name,'operation':'BLP1 header comment','comment':text}
    write_new(destination,result,report);return report

def folder_jobs(folder,destination,format,recursive=True,preserve=True,extensions=None):
    folder,destination=Path(folder).resolve(),Path(destination).resolve()
    extensions={s.lower() for s in (extensions or EXTENSIONS)}
    paths=folder.rglob('*') if recursive else folder.iterdir();jobs=[];targets=set()
    for source in sorted(paths):
        if not source.is_file() or source.suffix.lower() not in extensions:continue
        if destination!=folder and destination in source.parents:continue
        relative=source.relative_to(folder) if preserve else Path(source.name)
        target=(destination/relative).with_suffix(FORMATS[format])
        if target in targets:raise ValueError(f'Output name collision: {target.name}. Preserve folder structure or narrow input types.')
        targets.add(target);jobs.append((source,target))
    return jobs
