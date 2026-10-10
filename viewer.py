"""BLP Studio desktop viewer. Zoom and stored mipmap selection are independent."""
import math,queue,threading,sys
from dataclasses import asdict,fields
from pathlib import Path
from PIL import Image,ImageTk,ImageDraw
from blp_studio import convert,inspect_blp,decode_mip
from preferences import Preferences
from formats import Options,FORMATS,load_image,parse_blp,get_comment,comment_capacity
from operations import optimize,save_comment,folder_jobs,EXTENSIONS

ZOOMS=(1,2,5,10,12.5,25,50,75,100,150,200,400,800,1600)

def display_scale(size,viewport,zoom):
    if zoom=='Fit':return max(0.0001,min(max(1,viewport[0]-24)/size[0],max(1,viewport[1]-24)/size[1]))
    return max(0.01,min(16,float(zoom.rstrip('%'))/100))

def mip_labels(info):
    return [f'{i}: {max(1,info["width"]>>i)} × {max(1,info["height"]>>i)}'+(' (original)' if i==0 else '') for i in range(info.get('mipmaps',1))]

def checker_tiles(rect,viewport):
    x,y,w,h=rect;vw,vh=viewport
    for gy in range(max(0,y),min(vh,y+h),12):
        for gx in range(max(0,x),min(vw,x+w),12):
            yield (gx,gy,min(gx+11,vw-1,x+w-1),min(gy+11,vh-1,y+h-1)),('#5c5c5c' if (gx//12+gy//12)%2 else '#909090')

def run_gui(initial_files=None):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    root=tk.Tk();root.title('BLP Studio');root.geometry('980x760');root.minsize(760,580)
    preferences=Preferences()
    try:options=Options(**preferences.data.get('export_options',{}))
    except (TypeError,ValueError):options=Options()
    cancellation=threading.Event()
    auto_size=tk.BooleanVar(value=bool(preferences.data.get('auto_size',False)))
    menu=tk.Menu(root);root.config(menu=menu)
    view_menu=tk.Menu(menu,tearoff=False);menu.add_cascade(label='View',menu=view_menu)
    def save_view():preferences.data['auto_size']=auto_size.get();preferences.save()
    view_menu.add_checkbutton(label='Resize window to image',variable=auto_size,command=save_view)
    help_menu=tk.Menu(menu,tearoff=False);menu.add_cascade(label='Help',menu=help_menu)
    def associate():
        import os,winreg
        if not getattr(sys,'frozen',False):messagebox.showinfo('File association','Use the packaged executable for Windows file association.');return
        if not messagebox.askyesno('Register BLP Studio','Register this copy as an Open With choice for BLP files? Existing default applications will stay unchanged.'):return
        executable=str(Path(sys.executable).resolve())
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Classes\BLPStudio.Texture') as key:winreg.SetValueEx(key,'',0,winreg.REG_SZ,'BLP texture')
        for suffix,value in [(r'DefaultIcon',f'"{executable}",0'),(r'shell\open\command',f'"{executable}" "%1"')]:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Classes\BLPStudio.Texture'+chr(92)+suffix) as key:winreg.SetValueEx(key,'',0,winreg.REG_SZ,value)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Classes\.blp\OpenWithProgids') as key:winreg.SetValueEx(key,'BLPStudio.Texture',0,winreg.REG_NONE,b'')
        messagebox.showinfo('Registered','BLP Studio is registered. Right-click a BLP, choose Open with, and select BLP Studio. You can choose it as the default there.')
    help_menu.add_command(label='Register for BLP files…',command=associate)
    help_menu.add_command(label='About',command=lambda:messagebox.showinfo('BLP Studio','BLP Studio\nStandalone texture viewer/converter\nBuilt-in BLP1/BLP2 and DDS encoders\nPillow image library; bundled Python and Tcl/Tk\nOriginal files are preserved.'))
    icon_path=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'Application.png'
    if icon_path.exists():
        root.application_icon=ImageTk.PhotoImage(Image.open(icon_path));root.iconphoto(True,root.application_icon)
    events=queue.Queue();files=[];current={};busy=False
    status=tk.StringVar(value='Open textures to view or convert them. Existing outputs are never overwritten.')
    zoom=tk.StringVar(value='Fit');mip=tk.StringVar();channel=tk.StringVar(value='RGBA')
    top=ttk.Frame(root,padding=10);top.pack(fill='x')
    ttk.Label(top,text='BLP Studio',font=('Segoe UI',15,'bold')).pack(side='left')
    ttk.Label(top,text='Standalone texture viewer and converter').pack(side='left',padx=16)
    actions=ttk.Frame(root,padding=(10,0));actions.pack(fill='x')
    export_bar=ttk.Frame(root,padding=(10,6));export_bar.pack(fill='x')
    output_format=tk.StringVar(value=options.format)
    ttk.Label(export_bar,text='Output format').pack(side='left')
    ttk.Combobox(export_bar,values=list(FORMATS),textvariable=output_format,state='readonly',width=20).pack(side='left',padx=8)
    progress_value=tk.DoubleVar(value=0)
    ttk.Progressbar(export_bar,variable=progress_value,maximum=100,length=150).pack(side='right')
    toolbar=ttk.Frame(root,padding=(10,8));toolbar.pack(fill='x')
    main=ttk.Panedwindow(root,orient='horizontal');main.pack(fill='both',expand=True,padx=10)
    listing=ttk.Frame(main);view=ttk.Frame(main);main.add(listing,weight=1);main.add(view,weight=4)
    lb=tk.Listbox(listing,width=25,exportselection=False);lb.pack(fill='both',expand=True)
    preview=ttk.Frame(view);preview.pack(fill='both',expand=True)
    canvas=tk.Canvas(preview,bg='#252525',highlightthickness=0)
    canvas.grid(row=0,column=0,sticky='nsew');preview.rowconfigure(0,weight=1);preview.columnconfigure(0,weight=1)
    horizontal=ttk.Scrollbar(preview,orient='horizontal');vertical=ttk.Scrollbar(preview,orient='vertical')
    horizontal.grid(row=1,column=0,sticky='ew');vertical.grid(row=0,column=1,sticky='ns')
    canvas.configure(xscrollcommand=horizontal.set,yscrollcommand=vertical.set)
    metadata=ttk.Label(view,text='',wraplength=680);metadata.pack(fill='x',pady=6)
    def selected_image():
        level=mip_box.current();level=max(0,level)
        if current.get('blp2'):
            if level not in current['cache']:current['cache'][level]=decode_mip(current['path'],level)
            return current['cache'][level]
        return current['image']
    def render(*_):
        if not current:return
        try:
            image=selected_image();vw,vh=max(1,canvas.winfo_width()),max(1,canvas.winfo_height())
            scale=display_scale(image.size,(vw,vh),zoom.get());sw,sh=max(1,round(image.width*scale)),max(1,round(image.height*scale))
            ox,oy=max(0,(vw-sw)//2),max(0,(vh-sh)//2)
            canvas.configure(scrollregion=(0,0,max(vw,sw),max(vh,sh)))
            x,y=canvas.canvasx(0),canvas.canvasy(0)
            # Render only the visible source crop; large zooms never allocate a
            # giant full-resolution preview buffer.
            left=max(0,math.floor((x-ox)/scale));top=max(0,math.floor((y-oy)/scale))
            right=min(image.width,math.ceil((x+vw-ox)/scale));bottom=min(image.height,math.ceil((y+vh-oy)/scale))
            background=Image.new('RGBA',(vw,vh),'#252525')
            if right>left and bottom>top:
                part=image.crop((left,top,right,bottom))
                if channel.get()=='Alpha':part=part.getchannel('A').convert('RGBA')
                elif channel.get()=='RGB':part=part.convert('RGB').convert('RGBA')
                part=part.resize((max(1,round((right-left)*scale)),max(1,round((bottom-top)*scale))),Image.Resampling.NEAREST if scale>=1 else Image.Resampling.LANCZOS)
                px,py=round(ox+left*scale-x),round(oy+top*scale-y)
                draw=ImageDraw.Draw(background)
                for bounds,color in checker_tiles((px,py,part.width,part.height),(vw,vh)):draw.rectangle(bounds,fill=color)
                background.alpha_composite(part,(px,py))
            canvas.photo=ImageTk.PhotoImage(background);canvas.delete('all')
            canvas.create_image(x,y,image=canvas.photo,anchor='nw')
            zoom_readout.config(text=f'{scale*100:g}% displayed')
        except Exception as exc:status.set(f'Preview error: {exc}')
    def scroll_x(*args):canvas.xview(*args);render()
    def scroll_y(*args):canvas.yview(*args);render()
    horizontal.config(command=scroll_x);vertical.config(command=scroll_y)
    def reset_view(*_):canvas.xview_moveto(0);canvas.yview_moveto(0);render()
    def change_zoom(direction):
        size=selected_image().size if current else (1,1)
        value=display_scale(size,(canvas.winfo_width(),canvas.winfo_height()),zoom.get())*100
        options=[z for z in ZOOMS if z>value+0.001] if direction>0 else [z for z in ZOOMS if z<value-0.001]
        zoom.set(f'{(min(options) if direction>0 else max(options)):g}%' if options else ('1600%' if direction>0 else '1%'))
    def select(_=None):
        indices=lb.curselection()
        if not indices:return
        path=files[indices[0]]
        try:
            rgba=load_image(path);rgba.load()
            is_blp2=path.suffix.lower() in ('.blp','.dds')
            info=inspect_blp(path) if is_blp2 else {'format':path.suffix.upper().lstrip('.'),'width':rgba.width,'height':rgba.height,'bytes':path.stat().st_size}
            current.clear();current.update(image=rgba,path=path,blp2=is_blp2,cache={0:rgba})
            if auto_size.get():root.geometry(f'{min(root.winfo_screenwidth()-80,max(900,rgba.width+280))}x{min(root.winfo_screenheight()-100,max(640,rgba.height+330))}')
            mip_box.config(values=mip_labels(info),state='readonly' if info.get('mipmaps',1)>1 else 'disabled');mip_box.current(0)
            metadata.config(text=path.name+'\n'+', '.join(f'{k}: {v}' for k,v in info.items()))
            status.set('Zoom changes display size. Mipmap selects a stored smaller image; level 0 is the original. Neither changes exported data.')
            zoom.set('Fit');reset_view()
        except Exception as exc:messagebox.showerror('Cannot open texture',str(exc))
    def open_files():
        paths=filedialog.askopenfilenames(initialdir=preferences.folder(),filetypes=[('Textures','*.blp *.png *.tga *.jpg *.jpeg *.bmp *.dds'),('All files','*.*')])
        for path in paths:
            p=Path(path)
            if p not in files:files.append(p);lb.insert('end',p.name)
        if paths:
            preferences.remember(paths[-1]);lb.selection_clear(0,'end');lb.selection_set(len(files)-1);select()
    def persist_options():
        options.format=output_format.get();preferences.data['export_options']=asdict(options);preferences.save()
    def run_jobs(jobs,operation='convert'):
        nonlocal busy
        if busy:return
        persist_options();selected_options=Options(**asdict(options));cancellation.clear()
        busy=True;progress_value.set(0);status.set('Processing and validating…')
        def worker():
            total=max(1,len(jobs))
            for index,(src,dest) in enumerate(jobs):
                if cancellation.is_set():break
                try:
                    if operation=='optimize':report=optimize(src,dest,selected_options.compress_palette)
                    else:report=convert(src,dest,selected_options,cancellation,lambda fraction:events.put(('progress','',100*(index+fraction)/total)))
                    events.put(('ok',dest.name,f'Saved {report["saved_bytes"]} bytes' if operation=='optimize' else ''))
                except Exception as exc:events.put(('error',src.name,str(exc)))
                events.put(('progress','',100*(index+1)/total))
            events.put(('done','',''))
        threading.Thread(target=worker,daemon=True).start()
    def export_one():
        if not current:return
        source=current['path'];ext=FORMATS[output_format.get()]
        path=filedialog.asksaveasfilename(initialfile=source.stem+'-converted'+ext,defaultextension=ext,filetypes=[(ext.upper(),'*'+ext)])
        if path:run_jobs([(source,Path(path))])
    def export_all():
        if not files:return
        folder=filedialog.askdirectory(title='Choose batch output folder')
        if folder:run_jobs([(p,Path(folder)/(p.stem+FORMATS[output_format.get()])) for p in files])
    def options_dialog():
        dialog=tk.Toplevel(root);dialog.title('Export options');dialog.transient(root)
        notebook=ttk.Notebook(dialog);notebook.pack(fill='both',expand=True,padx=12,pady=12)
        variables={};groups={'General':['mipmaps','alpha','resample','comment'],
          'Palette':['dither','compress_palette'],'JPEG':['jpeg_quality','progressive','merge_headers'],
          'PNG':['png_compression','png_filter'],'TGA':['tga_rle','tga_top_left','tga_cross_lines']}
        labels={'mipmaps':'Mip count (0 = full chain)','alpha':'Alpha handling','resample':'Mip resizing',
          'comment':'BLP1 header comment','dither':'Floyd–Steinberg dithering','compress_palette':'Trim unused palette entries',
          'jpeg_quality':'Quality (1–100)','progressive':'Progressive JPEG','merge_headers':'Merge BLP1 JPEG headers',
          'png_compression':'Compression (0–9)','png_filter':'PNG row filter','tga_rle':'Run-length encoding',
          'tga_top_left':'Top-left orientation','tga_cross_lines':'Allow RLE packets across row boundaries'}
        choices={'alpha':['Preserve','Opaque','Remove','Auto','Transparent border'],'resample':['Lanczos','Nearest'],
          'png_filter':['Adaptive','None','Sub','Up','Average','Paeth']}
        for group,names in groups.items():
            panel=ttk.Frame(notebook,padding=12);notebook.add(panel,text=group)
            for row,name in enumerate(names):
                value=getattr(options,name);var=tk.BooleanVar(value=value) if isinstance(value,bool) else tk.StringVar(value=str(value));variables[name]=var
                ttk.Label(panel,text=labels[name]).grid(row=row,column=0,sticky='w',pady=6)
                if isinstance(value,bool):widget=ttk.Checkbutton(panel,variable=var)
                elif name in choices:widget=ttk.Combobox(panel,textvariable=var,values=choices[name],state='readonly',width=28)
                else:widget=ttk.Entry(panel,textvariable=var,width=36)
                widget.grid(row=row,column=1,sticky='ew',padx=12)
        ttk.Label(dialog,text='Options apply only to their format. DXT1 has binary alpha; DXT3 has 16 alpha levels.\nComments require BLP1 and available unused header space.',padding=12).pack()
        def save():
            try:
                values={name:var.get() for name,var in variables.items()}
                for name in ('mipmaps','jpeg_quality','png_compression'):values[name]=int(values[name])
                if not 0<=values['mipmaps']<=16 or not 1<=values['jpeg_quality']<=100 or not 0<=values['png_compression']<=9:raise ValueError('Numeric option is outside its allowed range.')
                for name,value in values.items():setattr(options,name,value)
                persist_options();dialog.destroy()
            except ValueError as exc:messagebox.showerror('Invalid option',str(exc),parent=dialog)
        ttk.Button(dialog,text='Save options',command=save).pack(pady=(0,12))
    def browse_folder():
        folder=filedialog.askdirectory(initialdir=preferences.folder(),title='Browse texture folder')
        if not folder:return
        for p in sorted(Path(folder).iterdir()):
            if p.is_file() and p.suffix.lower() in EXTENSIONS and p not in files:files.append(p);lb.insert('end',p.name)
        preferences.remember(Path(folder)/'placeholder')
        if files:lb.selection_clear(0,'end');lb.selection_set(0);select()
    def batch_dialog():
        dialog=tk.Toplevel(root);dialog.title('Folder batch');dialog.transient(root);panel=ttk.Frame(dialog,padding=12);panel.pack(fill='both',expand=True)
        source=tk.StringVar(value=preferences.folder());target=tk.StringVar();recursive=tk.BooleanVar(value=True);preserve=tk.BooleanVar(value=True)
        types=tk.StringVar(value='blp png bmp tga jpg jpeg dds');mode=tk.StringVar(value='Convert')
        for row,(label,var) in enumerate([('Source folder',source),('Output folder',target)]):
            ttk.Label(panel,text=label).grid(row=row,column=0,sticky='w');ttk.Entry(panel,textvariable=var,width=50).grid(row=row,column=1,padx=8,pady=5)
            def choose(v=var):
                path=filedialog.askdirectory(initialdir=v.get() or preferences.folder(),parent=dialog)
                if path:v.set(path)
            ttk.Button(panel,text='Browse',command=choose).grid(row=row,column=2)
        ttk.Label(panel,text='Input extensions').grid(row=2,column=0,sticky='w');ttk.Entry(panel,textvariable=types).grid(row=2,column=1,sticky='ew',padx=8,pady=5)
        ttk.Checkbutton(panel,text='Include subfolders',variable=recursive).grid(row=3,column=1,sticky='w')
        ttk.Checkbutton(panel,text='Keep folder structure',variable=preserve).grid(row=4,column=1,sticky='w')
        ttk.Combobox(panel,values=['Convert','Optimize BLP'],textvariable=mode,state='readonly').grid(row=5,column=1,sticky='w',pady=6)
        def start():
            try:
                if not Path(source.get()).is_dir() or not target.get():raise ValueError('Choose valid source and output folders.')
                extensions={'.'+s.lower().lstrip('.') for s in types.get().replace(',',' ').split()}
                if mode.get()=='Optimize BLP':extensions={'.blp'}
                jobs=folder_jobs(source.get(),target.get(),'BLP2 DXT3' if mode.get()=='Optimize BLP' else output_format.get(),recursive.get(),preserve.get(),extensions)
                if not jobs:raise ValueError('No matching input files.')
                preferences.remember(Path(source.get())/'placeholder');run_jobs(jobs,'optimize' if mode.get()=='Optimize BLP' else 'convert');dialog.destroy()
            except Exception as exc:messagebox.showerror('Batch error',str(exc),parent=dialog)
        ttk.Button(panel,text='Start batch',command=start).grid(row=6,column=1,pady=12)
    def optimize_selected():
        if not current or current['path'].suffix.lower()!='.blp':messagebox.showinfo('Optimize','Open a BLP first.');return
        source=current['path'];target=filedialog.asksaveasfilename(initialfile=source.stem+'-optimized.blp',defaultextension='.blp')
        if target:run_jobs([(source,Path(target))],'optimize')
    def comments_dialog():
        if not current or current['path'].suffix.lower()!='.blp':messagebox.showinfo('Comments','Open a BLP1 first.');return
        source=current['path'];data=source.read_bytes();capacity=comment_capacity(data)
        if not capacity:messagebox.showinfo('Comments','This file has no available BLP1 header comment space.');return
        dialog=tk.Toplevel(root);dialog.title('BLP1 header comment');dialog.transient(root)
        ttk.Label(dialog,text=f'{capacity} UTF-8 bytes available. Saved in unused header space; file size stays the same.',padding=10).pack()
        text=tk.Text(dialog,width=60,height=6);text.pack(padx=10);text.insert('1.0',get_comment(data))
        def save():
            value=text.get('1.0','end-1c');target=filedialog.asksaveasfilename(initialfile=source.stem+'-commented.blp',defaultextension='.blp',parent=dialog)
            if target:
                try:save_comment(source,target,value);status.set('Header comment saved.');dialog.destroy()
                except Exception as exc:messagebox.showerror('Comment error',str(exc),parent=dialog)
        ttk.Button(dialog,text='Save copy',command=save).pack(pady=10)
    def details():
        if not current:return
        import json
        path=current['path'];info=inspect_blp(path) if path.suffix.lower() in ('.blp','.dds') else {}
        if path.suffix.lower() not in ('.blp','.dds'):
            with Image.open(path) as im:info.update(format=im.format,mode=im.mode,size=im.size,**{k:(f'{len(v)} bytes' if isinstance(v,bytes) else str(v)[:300]) for k,v in im.info.items()})
        elif path.suffix.lower()=='.blp':info['stored_header_comment']=get_comment(path.read_bytes())
        info['filename']=path.name;info['bytes']=path.stat().st_size
        dialog=tk.Toplevel(root);dialog.title('Texture details');text=tk.Text(dialog,width=76,height=22);text.pack(fill='both',expand=True);text.insert('1.0',json.dumps(info,indent=2,ensure_ascii=False));text.config(state='disabled')
    for index,(label,command) in enumerate([('Open textures',open_files),('Convert selected',export_one),('Convert all',export_all),('Folder batch',batch_dialog),('Browse folder',browse_folder),('Optimize BLP',optimize_selected),('Comments',comments_dialog),('Details',details)]):
        ttk.Button(actions,text=label,command=command).grid(row=index//4,column=index%4,padx=(0,6),pady=3,sticky='ew')
    ttk.Button(export_bar,text='Export options',command=options_dialog).pack(side='left')
    ttk.Button(export_bar,text='Cancel',command=cancellation.set).pack(side='left',padx=8)
    ttk.Label(toolbar,text='Zoom').pack(side='left')
    ttk.Button(toolbar,text='−',width=3,command=lambda:change_zoom(-1)).pack(side='left',padx=(6,2))
    ttk.Combobox(toolbar,values=['Fit']+[f'{z:g}%' for z in ZOOMS],textvariable=zoom,width=7,state='readonly').pack(side='left')
    ttk.Button(toolbar,text='+',width=3,command=lambda:change_zoom(1)).pack(side='left',padx=2)
    ttk.Button(toolbar,text='Fit',command=lambda:zoom.set('Fit')).pack(side='left')
    ttk.Button(toolbar,text='100%',command=lambda:zoom.set('100%')).pack(side='left',padx=(2,12))
    ttk.Label(toolbar,text='Mipmap').pack(side='left')
    mip_box=ttk.Combobox(toolbar,textvariable=mip,width=23,state='disabled');mip_box.pack(side='left',padx=6)
    ttk.Combobox(toolbar,values=['RGBA','RGB','Alpha'],textvariable=channel,width=6,state='readonly').pack(side='left')
    zoom_readout=ttk.Label(toolbar,text='');zoom_readout.pack(side='left',padx=8)
    zoom.trace_add('write',reset_view);channel.trace_add('write',render);mip_box.bind('<<ComboboxSelected>>',reset_view)
    lb.bind('<<ListboxSelect>>',select);canvas.bind('<Configure>',render)
    canvas.bind('<MouseWheel>',lambda event:change_zoom(1 if event.delta>0 else -1))
    root.bind('<Control-plus>',lambda event:change_zoom(1));root.bind('<Control-minus>',lambda event:change_zoom(-1))
    def next_file(direction):
        if not files:return
        index=lb.curselection();index=(index[0] if index else 0)+direction;index=max(0,min(len(files)-1,index))
        lb.selection_clear(0,'end');lb.selection_set(index);lb.see(index);select()
    root.bind('<Control-Right>',lambda event:next_file(1));root.bind('<Control-Left>',lambda event:next_file(-1))
    log=tk.Text(root,height=4,state='disabled');log.pack(fill='x',padx=10,pady=(8,0))
    ttk.Label(root,textvariable=status,wraplength=940,padding=10).pack(fill='x')
    def poll():
        nonlocal busy
        try:
            while True:
                kind,name,detail=events.get_nowait()
                if kind=='done':busy=False;status.set('Cancelled.' if cancellation.is_set() else 'Finished. Results are listed above.')
                elif kind=='progress':progress_value.set(detail)
                else:
                    log.config(state='normal');log.insert('end',f'{kind.upper()}: {name}\n'+(detail+'\n' if detail else ''));log.see('end');log.config(state='disabled')
        except queue.Empty:pass
        root.after(100,poll)
    def add_paths(paths):
        added=[]
        for name in paths:
            path=Path(name)
            candidates=sorted(path.iterdir()) if path.is_dir() else [path]
            for item in candidates:
                if item.is_file() and item.suffix.lower() in EXTENSIONS and item not in files:
                    files.append(item);lb.insert('end',item.name);added.append(item)
        if added:
            preferences.remember(added[-1]);lb.selection_clear(0,'end');lb.selection_set(files.index(added[-1]));select()
    def initial_open():
        add_paths(initial_files or [])
        try:
            from windows_drop import install
            install(root,add_paths)
        except Exception as exc:status.set('File drop could not be enabled: '+str(exc))
    root.after(0,initial_open);poll();root.mainloop()
