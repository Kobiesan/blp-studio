"""BLP/DDS codecs, configurable raster exports and lossless BLP repacking."""
import io,math,struct,zlib
from dataclasses import dataclass,asdict
from pathlib import Path
from PIL import Image
from blp_codec import block,distance,expand

FORMATS={'BLP2 DXT1':'.blp','BLP2 DXT3':'.blp','BLP2 DXT5':'.blp','BLP2 Paletted':'.blp',
         'BLP1 Paletted':'.blp','BLP1 JPEG':'.blp','PNG':'.png','JPEG':'.jpg','BMP':'.bmp',
         'TGA True Color':'.tga','TGA Paletted':'.tga','DDS True Color':'.dds',
         'DDS DXT1':'.dds','DDS DXT3':'.dds','DDS DXT5':'.dds'}

@dataclass
class Options:
    format:str='BLP2 DXT3'
    mipmaps:int=0 # 0 = complete chain
    alpha:str='Preserve'
    dither:bool=False
    compress_palette:bool=False
    jpeg_quality:int=85
    progressive:bool=False
    merge_headers:bool=True
    png_compression:int=6
    png_filter:str='Adaptive'
    tga_rle:bool=True
    tga_top_left:bool=True
    tga_cross_lines:bool=False
    resample:str='Lanczos'
    comment:str=''

def levels(image,count=0,resample='Lanczos'):
    maximum=int(math.log2(max(image.size)))+1
    count=maximum if not count else min(maximum,max(1,count))
    method=Image.Resampling.LANCZOS if resample=='Lanczos' else Image.Resampling.NEAREST
    return [image.resize((max(1,image.width>>i),max(1,image.height>>i)),method) for i in range(count)]

def transform_alpha(image,mode):
    image=image.convert('RGBA')
    if mode in ('Opaque','Remove'):image.putalpha(255)
    elif mode=='Auto' and image.getchannel('A').getextrema() in ((0,0),(255,255)):image.putalpha(255)
    elif mode=='Transparent border':
        alpha=image.getchannel('A');from PIL import ImageDraw
        ImageDraw.Draw(alpha).rectangle((0,0,image.width-1,image.height-1),outline=0);image.putalpha(alpha)
    return image

def dxt_block(pixels,kind):
    encoded=block(pixels);colors=encoded[8:]
    if kind=='DXT3':return encoded
    if kind=='DXT5':
        values=[p[3] for p in pixels];hi,lo=max(values),min(values)
        palette=[hi,lo]+[( (7-i)*hi+i*lo)//7 for i in range(1,7)] if hi>lo else [hi,lo,hi,hi,hi,hi,0,255]
        bits=sum(min(range(8),key=lambda k:abs(values[i]-palette[k]))<<(i*3) for i in range(16))
        return bytes((hi,lo))+bits.to_bytes(6,'little')+colors
    if any(p[3]<128 for p in pixels):
        c0,c1=sorted(struct.unpack_from('<HH',colors));a,b=expand(c0),expand(c1)
        palette=[a,b,tuple((x+y)//2 for x,y in zip(a,b))]
        indexes=sum((3 if p[3]<128 else min(range(3),key=lambda k:distance(p[:3],palette[k])))<<(2*i) for i,p in enumerate(pixels))
        return struct.pack('<HHI',c0,c1,indexes)
    return colors

def compress_dxt(image,kind,cancel=None,progress=None):
    pixels=image.convert('RGBA').load();w,h=image.size;out=bytearray()
    for y in range(0,h,4):
        if cancel and cancel.is_set():raise InterruptedError('Conversion cancelled.')
        # Use Pillow's bundled native BCn encoder, with no external executable.
        # Four-row strips keep cancellation responsive and bound memory usage.
        strip=image.crop((0,y,w,min(y+4,h))).convert('RGBA')
        pw,ph=max(4,(w+3)//4*4),4
        padded=Image.new('RGBA',(pw,ph));padded.paste(strip)
        if pw>w:padded.paste(strip.crop((w-1,0,w,strip.height)).resize((pw-w,strip.height),Image.Resampling.NEAREST),(w,0))
        if strip.height<4:padded.paste(padded.crop((0,strip.height-1,pw,strip.height)).resize((pw,4-strip.height),Image.Resampling.NEAREST),(0,strip.height))
        try:
            buffer=io.BytesIO();padded.save(buffer,'DDS',pixel_format=kind);payload=bytearray(buffer.getvalue()[128:]);block_size=8 if kind=='DXT1' else 16
            # The bundled BCn alpha writer drops the last texel in a block.
            # Keep its fast RGB fit, but encode every alpha texel ourselves.
            for x in range(0,w,4):
                samples=[pixels[min(x+dx,w-1),min(y+dy,h-1)] for dy in range(4) for dx in range(4)];offset=x//4*block_size
                if kind=='DXT1':
                    if any(p[3]<128 for p in samples):payload[offset:offset+8]=dxt_block(samples,kind)
                elif kind=='DXT3':payload[offset:offset+8]=sum(min(15,(p[3]+8)//17)<<(4*i) for i,p in enumerate(samples)).to_bytes(8,'little')
                else:
                    values=[p[3] for p in samples];hi,lo=max(values),min(values)
                    palette=[hi,lo]+[((7-i)*hi+i*lo)//7 for i in range(1,7)] if hi>lo else [hi,lo,hi,hi,hi,hi,0,255]
                    bits=sum(min(range(8),key=lambda k:abs(values[i]-palette[k]))<<(i*3) for i in range(16))
                    payload[offset:offset+8]=bytes((hi,lo))+bits.to_bytes(6,'little')
            out.extend(payload)
        except OSError:
            for x in range(0,w,4):out.extend(dxt_block([pixels[min(x+dx,w-1),min(y+dy,h-1)] for dy in range(4) for dx in range(4)],kind))
        if progress:progress(min(1,(y+4)/h))
    return bytes(out)

def dds_header(w,h,payload_size,count,kind):
    raw=kind in ('RGB','RGBA')
    flags=0x1007|(8 if raw else 0x80000)|(0x20000 if count>1 else 0)
    pf=([32,0x41 if kind=='RGBA' else 0x40,0,32 if kind=='RGBA' else 24,0xff0000,0xff00,0xff,0xff000000 if kind=='RGBA' else 0] if raw else [32,4,int.from_bytes(kind.encode(),'little'),0,0,0,0,0])
    return b'DDS '+struct.pack('<31I',124,flags,h,w,payload_size,0,count,*([0]*11),*pf,0x1000|(0x400008 if count>1 else 0),0,0,0,0)

def palette_data(image,mips,dither,compressed=False):
    palette=image.convert('RGB').quantize(colors=256)
    rgba=palette.getpalette()[:768];rgba+= [0]*(768-len(rgba))
    indexes=[m.convert('RGB').quantize(palette=palette,dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE).tobytes() for m in mips]
    used=max(max(data) for data in indexes)+1 if compressed else 256
    raw=b''.join(bytes((rgba[i*3+2],rgba[i*3+1],rgba[i*3],0)) for i in range(used))
    return raw,indexes

def jpeg_mip(image,quality,progressive):
    # BLP JPEG stores B,G,R,A as four JPEG components. CMYK mode provides four
    # components; undo Pillow/libjpeg's inverted-CMYK convention on decoding.
    r,g,b,a=image.split();buffer=io.BytesIO()
    # Pillow writes CMYK with inverted samples; invert beforehand to store raw
    # B,G,R,A planes. BLP streams carry no Adobe colour-transform marker.
    Image.merge('CMYK',tuple(band.point(lambda value:255-value) for band in (b,g,r,a))).save(buffer,'JPEG',quality=quality,progressive=progressive)
    data=buffer.getvalue();out=bytearray(data[:2]);pos=2
    while pos+4<=len(data) and data[pos]==255:
        marker=data[pos+1]
        if marker==0xda:out.extend(data[pos:]);break
        length=int.from_bytes(data[pos+2:pos+4],'big');segment=data[pos:pos+2+length]
        if marker!=0xee:out.extend(segment)
        pos+=2+length
    return bytes(out)

def make_blp(image,options,cancel=None,progress=None):
    w,h=image.size
    if not w or not h or max(w,h)>16384:raise ValueError('BLP dimensions must be between 1 and 16384 pixels.')
    mips=levels(image,options.mipmaps,options.resample);has_alpha=options.alpha=='Opaque' or image.getchannel('A').getextrema()!=(255,255)
    fmt=options.format;blp1=fmt.startswith('BLP1');prefix=b''
    if 'Paletted' in fmt:
        prefix,indexes=palette_data(image,mips,options.dither,options.compress_palette)
        payloads=[idx+(m.getchannel('A').tobytes() if has_alpha else b'') for idx,m in zip(indexes,mips)]
        compression=1;encoding=1;alpha=8 if has_alpha else 0;alpha_encoding=8
    elif blp1:
        payloads=[jpeg_mip(m,options.jpeg_quality,options.progressive) for m in mips]
        shared=b''
        if options.merge_headers:
            length=0
            for values in zip(*payloads):
                if len(set(values))>1:break
                length+=1
            shared=payloads[0][:length];payloads=[p[length:] for p in payloads]
        prefix=struct.pack('<I',len(shared))+shared;compression=0;alpha=8 if has_alpha else 0
    else:
        kind=fmt.split()[-1];payloads=[compress_dxt(dither_565(m) if options.dither else m,kind,cancel,progress) for m in mips]
        compression=1;encoding=2;alpha=(1 if kind=='DXT1' else 8) if has_alpha else 0;alpha_encoding={'DXT1':0,'DXT3':1,'DXT5':7}[kind]
    base=156 if blp1 else 148;offsets=[];pos=base+len(prefix)
    for data in payloads:offsets.append(pos);pos+=len(data)
    offsets+= [0]*(16-len(offsets));sizes=[len(p) for p in payloads]+[0]*(16-len(payloads))
    if blp1:header=struct.pack('<4s6I32I',b'BLP1',compression,alpha,w,h,4 if has_alpha else 5,1,*offsets,*sizes)
    else:header=struct.pack('<4sI4BII32I',b'BLP2',compression,encoding,alpha,alpha_encoding,int(len(mips)>1),w,h,*offsets,*sizes)
    data=header+prefix+b''.join(payloads)
    if blp1 and options.comment:data=set_comment(data,options.comment)
    return data

def parse_blp(data):
    if len(data)<148 or data[:4] not in (b'BLP1',b'BLP2'):raise ValueError('Invalid BLP header.')
    version=1 if data[:4]==b'BLP1' else 2
    if version==1:
        if len(data)<156:raise ValueError('Truncated BLP1 header.')
        compression,alpha,w,h,picture,sub=struct.unpack_from('<6I',data,4);base=156;offset_at=28;encoding=1 if compression else 0;alpha_encoding=picture
    else:
        compression,encoding,alpha,alpha_encoding,mips,w,h=struct.unpack_from('<I4BII',data,4);base=148;offset_at=20
    if w<1 or h<1 or max(w,h)>16384 or alpha not in (0,1,4,8):raise ValueError('Invalid texture dimensions or alpha depth.')
    offsets=struct.unpack_from('<16I',data,offset_at);sizes=struct.unpack_from('<16I',data,offset_at+64)
    count=0
    for offset,size in zip(offsets,sizes):
        if not offset:break
        if offset<base or not size or offset+size>len(data):raise ValueError('Invalid mip range.')
        count+=1
    if count<1:raise ValueError('No mip data.')
    return dict(format=f'BLP{version}',version=version,compression=compression,encoding=encoding,alpha_bits=alpha,alpha_encoding=alpha_encoding,width=w,height=h,mipmaps=count,bytes=len(data),offsets=offsets[:count],sizes=sizes[:count],base=base,offset_at=offset_at)

def unpack_alpha(data,n,bits):
    if not bits:return bytes([255])*n
    if len(data)<(n*bits+7)//8:raise ValueError('Truncated alpha plane.')
    if bits==8:return data[:n]
    maximum=(1<<bits)-1
    return bytes(((data[i*bits//8]>>((i*bits)%8))&maximum)*255//maximum for i in range(n))

def decode_blp(data,level=0):
    info=parse_blp(data)
    if not 0<=level<info['mipmaps']:raise ValueError('Invalid mip level.')
    w,h=max(1,info['width']>>level),max(1,info['height']>>level);n=w*h
    offset,size=info['offsets'][level],info['sizes'][level];payload=data[offset:offset+size];base=info['base']
    if info['compression']==0:
        length=struct.unpack_from('<I',data,base)[0]
        with Image.open(io.BytesIO(data[base+4:base+4+length]+payload)) as image:
            if image.mode=='CMYK':
                # Read the stored components without Pillow's normal CMYK inversion.
                args=image.tile[0].args;image.tile=[image.tile[0]._replace(args=('CMYK',args[1]))]
                b,g,r,a=image.split()
                if not info['alpha_bits']:a=Image.new('L',(w,h),255)
                return Image.merge('RGBA',(r,g,b,a))
            b,g,r=image.convert('RGB').split();return Image.merge('RGBA',(r,g,b,Image.new('L',(w,h),255)))
    if info['encoding']==1:
        palette_count=min(256,(min(info['offsets'])-base)//4);palette=data[base:base+palette_count*4]
        if len(payload)<n:raise ValueError('Truncated palette indices.')
        alpha=unpack_alpha(payload[n:],n,info['alpha_bits']) if info['alpha_bits'] else bytes([255])*n
        out=bytearray()
        for i,index in enumerate(payload[:n]):
            if index>=palette_count:raise ValueError('Index outside palette.')
            b,g,r,a=palette[index*4:index*4+4]
            if info['version']==1 and info['alpha_encoding']==5 and info['alpha_bits']:a=255-a
            else:a=alpha[i]
            out.extend((r,g,b,a))
        return Image.frombytes('RGBA',(w,h),bytes(out))
    if info['encoding']==3:return Image.frombytes('RGBA',(w,h),payload[:n*4],'raw','BGRA')
    kind={0:'DXT1',1:'DXT3',7:'DXT5'}.get(info['alpha_encoding'])
    if not kind:raise ValueError('Unsupported DXTC variant.')
    with Image.open(io.BytesIO(dds_header(w,h,len(payload),1,kind)+payload)) as image:return image.convert('RGBA')

def load_image(path,level=0):
    path=Path(path)
    if path.suffix.lower()=='.blp':return decode_blp(path.read_bytes(),level)
    if path.suffix.lower()=='.dds':return decode_dds(path.read_bytes(),level)
    return decode_raster(path)

def parse_dds(data):
    if len(data)<128 or data[:4]!=b'DDS ':raise ValueError('Invalid DDS header.')
    h,w=struct.unpack_from('<II',data,12);count=max(1,struct.unpack_from('<I',data,28)[0]);depth=struct.unpack_from('<I',data,24)[0]
    caps2=struct.unpack_from('<I',data,112)[0];fourcc=data[84:88];bitcount=struct.unpack_from('<I',data,88)[0]
    if caps2 or depth>1:raise ValueError('Cube, volume and array DDS are not supported.')
    if min(w,h)<1 or max(w,h)>16384 or count>16:raise ValueError('Invalid DDS dimensions/mips.')
    base=128;block_size={'DXT1':8,'DXT3':16,'DXT5':16,'ATI1':8,'ATI2':16,'BC4U':8,'BC5U':16}.get(fourcc.decode('ascii',errors='replace'))
    if fourcc==b'DX10':
        if len(data)<148:raise ValueError('Truncated DX10 DDS header.')
        fmt,dimension,misc,array,alpha=struct.unpack_from('<5I',data,128)
        if dimension!=3 or misc&4 or array>1:raise ValueError('Cube, volume and array DDS are not supported.')
        base=148;block_size=8 if fmt in (70,71,72,79,80,81) else 16 if fmt in (73,74,75,76,77,78,82,83,84,94,95,96,97,98,99) else None
        if block_size is None:bitcount=32 if fmt in (28,29,87,91) else bitcount
    offsets=[];sizes=[];pos=base
    for i in range(count):
        mw,mh=max(1,w>>i),max(1,h>>i);size=max(1,(mw+3)//4)*max(1,(mh+3)//4)*block_size if block_size else mw*mh*(bitcount//8)
        if not size or pos+size>len(data):raise ValueError('Invalid or unsupported DDS mip data.')
        offsets.append(pos);sizes.append(size);pos+=size
    return dict(format='DDS',width=w,height=h,mipmaps=count,encoding=fourcc.decode('ascii',errors='replace').strip('\0') or f'Raw {bitcount}-bit',bytes=len(data),offsets=offsets,sizes=sizes,base=base,block_size=block_size,bitcount=bitcount)

def decode_dds(data,level=0):
    info=parse_dds(data)
    if not 0<=level<info['mipmaps']:raise ValueError('Invalid DDS mip level.')
    w,h=max(1,info['width']>>level),max(1,info['height']>>level);header=bytearray(data[:info['base']])
    struct.pack_into('<II',header,12,h,w);struct.pack_into('<I',header,20,info['sizes'][level] if info['block_size'] else w*(info['bitcount']//8));struct.pack_into('<I',header,28,1)
    offset=info['offsets'][level];return decode_raster(io.BytesIO(bytes(header)+data[offset:offset+info['sizes'][level]]))

def decode_raster(source):
    with Image.open(source) as image:
        # Pillow's TGA plugin leaves 32-bit BGRA palette mode at RGB. Correct
        # that metadata before loading so valid paletted alpha TGA can decode.
        if image.format=='TGA' and image.palette and image.palette.rawmode=='BGRA':image.palette.mode='RGBA'
        return image.convert('RGBA')

def comment_capacity(data):
    info=parse_blp(data)
    return max(0,(15-info['mipmaps'])*8-6) if info['version']==1 else 0

def get_comment(data):
    info=parse_blp(data)
    if info['version']!=1:return ''
    start=info['mipmaps']+1;raw=data[28+start*4:92]+data[92+start*4:156]
    if raw[:4]!=b'BCMT':return ''
    return raw[6:6+int.from_bytes(raw[4:6],'little')].decode('utf-8',errors='replace')

def set_comment(data,text):
    info=parse_blp(data);encoded=text.encode('utf-8');capacity=comment_capacity(data)
    if info['version']!=1:raise ValueError('Embedded header comments require BLP1.')
    if len(encoded)>capacity:raise ValueError(f'Comment exceeds {capacity} UTF-8 bytes available in unused header slots.')
    start=info['mipmaps']+1;size=(16-start)*4;raw=b'BCMT'+len(encoded).to_bytes(2,'little')+encoded;raw=raw.ljust(size*2,b'\0')
    out=bytearray(data);out[28+start*4:92]=raw[:size];out[92+start*4:156]=raw[size:]
    return bytes(out)

def optimize_blp(data,compress_palette=True):
    info=parse_blp(data);base=info['base'];prefix=data[base:min(info['offsets'])]
    if info['encoding']==1 and info['compression']==1 and compress_palette:
        maximum=max(max(data[o:o+max(1,info['width']>>i)*max(1,info['height']>>i)]) for i,o in enumerate(info['offsets']))+1
        prefix=prefix[:maximum*4]
    header=bytearray(data[:base]);pos=base+len(prefix);parts=[]
    for i,(offset,size) in enumerate(zip(info['offsets'],info['sizes'])):
        payload=data[offset:offset+size];struct.pack_into('<I',header,info['offset_at']+i*4,pos);parts.append(payload);pos+=len(payload)
    return bytes(header)+prefix+b''.join(parts)

def png_bytes(image,compression=6,filter_name='Adaptive',cancel=None,progress=None):
    image=image.convert('RGB' if image.mode=='RGB' else 'RGBA');w,h=image.size;channels=len(image.getbands());rows=[];previous=bytes(w*channels)
    if filter_name=='Adaptive':
        if cancel and cancel.is_set():raise InterruptedError('Conversion cancelled.')
        buffer=io.BytesIO();image.save(buffer,'PNG',compress_level=compression)
        if progress:progress(1)
        return buffer.getvalue()
    def paeth(a,b,c):
        p=a+b-c;ds=(abs(p-a),abs(p-b),abs(p-c));return (a,b,c)[ds.index(min(ds))]
    choices={'None':0,'Sub':1,'Up':2,'Average':3,'Paeth':4}
    raw=image.tobytes()
    for y in range(h):
        if cancel and cancel.is_set():raise InterruptedError('Conversion cancelled.')
        row=raw[y*w*channels:(y+1)*w*channels];candidates=[]
        for mode in ([choices[filter_name]] if filter_name in choices else range(5)):
            values=bytearray()
            for x,v in enumerate(row):
                a=row[x-channels] if x>=channels else 0;b=previous[x];c=previous[x-channels] if x>=channels else 0
                predictor=(0,a,b,(a+b)//2,paeth(a,b,c))[mode];values.append((v-predictor)&255)
            candidates.append((sum(min(v,256-v) for v in values),bytes([mode])+values))
        rows.append(min(candidates,key=lambda p:p[0])[1]);previous=row
        if progress:progress((y+1)/h)
    def chunk(tag,payload):return struct.pack('>I',len(payload))+tag+payload+struct.pack('>I',zlib.crc32(tag+payload)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6 if channels==4 else 2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows),compression))+chunk(b'IEND',b'')

def tga_bytes(image,options):
    alpha=image.mode!='RGB';image=image.convert('RGBA');w,h=image.size;paletted=options.format=='TGA Paletted'
    if paletted:
        q=image.quantize(colors=256,method=Image.Quantize.FASTOCTREE)
        if options.dither:
            palette=Image.new('P',(1,1));palette.putpalette(q.getpalette('RGB'))
            indexes=image.convert('RGB').quantize(palette=palette,dither=Image.Dither.FLOYDSTEINBERG)
            q.putdata(indexes.getdata())
        colors=q.getpalette('RGBA');indexes=q.tobytes();count=max(indexes)+1 if options.compress_palette else 256
        palette=b''.join(bytes((colors[i*4+2],colors[i*4+1],colors[i*4]))+(bytes([colors[i*4+3]]) if alpha else b'') for i in range(count))
        units=[bytes([v]) for v in indexes];depth=8;kind=1
    else:
        palette=b'';count=0;units=[bytes((b,g,r,a)) if alpha else bytes((b,g,r)) for r,g,b,a in image.getdata()];depth=32 if alpha else 24;kind=2
    if not options.tga_top_left:units=[p for y in reversed(range(h)) for p in units[y*w:(y+1)*w]]
    payload=bytearray()
    if options.tga_rle:
        for row in ([units] if options.tga_cross_lines else [units[y*w:(y+1)*w] for y in range(h)]):
            i=0
            while i<len(row):
                run=1
                while run<128 and i+run<len(row) and row[i+run]==row[i]:run+=1
                if run>1:payload.extend(bytes([0x80+run-1])+row[i]);i+=run
                else:
                    start=i;i+=1
                    while i<len(row) and i-start<128 and (i+1>=len(row) or row[i]!=row[i+1]):i+=1
                    payload.append(i-start-1);payload.extend(b''.join(row[start:i]))
        kind+=8
    else:payload.extend(b''.join(units))
    header=struct.pack('<BBBHHBHHHHBB',0,int(paletted),kind,0,count,(32 if alpha else 24) if paletted else 0,0,0,w,h,depth,(0x20 if options.tga_top_left else 0)|(8 if alpha and not paletted else 0))
    return header+palette+payload

def encode_image(image,options,cancel=None,progress=None):
    remove_alpha=options.alpha=='Remove' or (options.alpha=='Auto' and image.convert('RGBA').getchannel('A').getextrema() in ((0,0),(255,255)))
    image=transform_alpha(image,options.alpha);fmt=options.format
    if fmt.startswith('BLP'):return make_blp(image,options,cancel,progress)
    if fmt=='PNG':return png_bytes(image.convert('RGB') if remove_alpha else image,options.png_compression,options.png_filter,cancel,progress)
    if fmt.startswith('TGA'):return tga_bytes(image.convert('RGB') if remove_alpha else image,options)
    if fmt.startswith('DDS'):
        mips=levels(image,options.mipmaps,options.resample);kind=fmt.split()[-1]
        payloads=[m.convert('RGB').tobytes('raw','BGR') if kind=='Color' and remove_alpha else m.tobytes('raw','BGRA') if kind=='Color' else compress_dxt(dither_565(m) if options.dither else m,kind,cancel,progress) for m in mips]
        return dds_header(image.width,image.height,len(payloads[0]) if kind!='Color' else image.width*(3 if remove_alpha else 4),len(mips),('RGB' if remove_alpha else 'RGBA') if kind=='Color' else kind)+b''.join(payloads)
    buffer=io.BytesIO()
    if fmt=='JPEG':image.convert('RGB').save(buffer,'JPEG',quality=options.jpeg_quality,progressive=options.progressive)
    elif fmt=='BMP':
        if remove_alpha:image.convert('RGB').save(buffer,'BMP')
        else:
            payload=image.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes('raw','BGRA')
            dib=struct.pack('<IiiHHIIiiII',108,image.width,image.height,1,32,3,len(payload),0,0,0,0)+struct.pack('<5I',0xff0000,0xff00,0xff,0xff000000,0x73524742)+bytes(48)
            return b'BM'+struct.pack('<IHHI',122+len(payload),0,0,122)+dib+payload
    else:raise ValueError('Unknown output format.')
    return buffer.getvalue()

def dither_565(image):
    """Floyd–Steinberg error diffusion before RGB565 compression; alpha intact."""
    image=image.convert('RGBA');w,h=image.size;values=[list(p) for p in image.getdata()];result=[]
    for y in range(h):
        for x in range(w):
            index=y*w+x;old=values[index];color=expand(__import__('blp_codec').rgb565(tuple(max(0,min(255,v)) for v in old[:3])))
            result.append((*color,old[3]))
            for dx,dy,factor in ((1,0,7/16),(-1,1,3/16),(0,1,5/16),(1,1,1/16)):
                nx,ny=x+dx,y+dy
                if 0<=nx<w and ny<h:
                    for k in range(3):values[ny*w+nx][k]+=(old[k]-color[k])*factor
    out=Image.new('RGBA',(w,h));out.putdata(result);return out
