"""RGB565 endpoint fitting and fallback DXT block encoding."""
import struct

def rgb565(rgb):
    r,g,b=rgb
    return (round(r*31/255)<<11)|(round(g*63/255)<<5)|round(b*31/255)

def expand(value):
    # Match Pillow's independent DXT decoder's RGB565 expansion.
    return ((value>>11)*255//31,((value>>5)&63)*255//63,(value&31)*255//31)

def distance(a,b):return sum((x-y)**2 for x,y in zip(a,b))

def block(pixels):
    colors=[p[:3] for p in pixels]
    visible=[p[:3] for p in pixels if p[3]>0] or colors
    center=tuple(sum(c[k] for c in visible)/len(visible) for k in range(3))
    first=max(visible,key=lambda c:distance(c,center))
    second=max(visible,key=lambda c:distance(c,first))
    a,b=first,second
    # Fit endpoints to palette assignments, retaining a valid opaque DXT palette.
    for _ in range(3):
        c0,c1=sorted((rgb565(a),rgb565(b)),reverse=True)
        a,b=expand(c0),expand(c1)
        palette=[a,b,tuple((2*x+y)//3 for x,y in zip(a,b)),tuple((x+2*y)//3 for x,y in zip(a,b))]
        indices=[min(range(4),key=lambda i:distance(color,palette[i])) for color in colors]
        weights=[(1,0),(0,1),(2/3,1/3),(1/3,2/3)]
        aa=ab=bb=0;ac=[0.,0.,0.];bc=[0.,0.,0.]
        for p,index in zip(pixels,indices):
            if not p[3]:continue
            u,v=weights[index];aa+=u*u;ab+=u*v;bb+=v*v
            for k in range(3):ac[k]+=u*p[k];bc[k]+=v*p[k]
        determinant=aa*bb-ab*ab
        if determinant<1e-8:break
        a=tuple(max(0,min(255,(ac[k]*bb-bc[k]*ab)/determinant)) for k in range(3))
        b=tuple(max(0,min(255,(bc[k]*aa-ac[k]*ab)/determinant)) for k in range(3))
    c0,c1=sorted((rgb565(a),rgb565(b)),reverse=True)
    a,b=expand(c0),expand(c1)
    palette=[a,b,tuple((2*x+y)//3 for x,y in zip(a,b)),tuple((x+2*y)//3 for x,y in zip(a,b))]
    indexes=sum(min(range(4),key=lambda i:distance(p[:3],palette[i]))<<(2*j) for j,p in enumerate(pixels))
    alpha=sum(min(15,(p[3]+8)//17)<<(4*j) for j,p in enumerate(pixels))
    return struct.pack('<QHHI',alpha,c0,c1,indexes)
