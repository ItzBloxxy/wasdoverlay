"""
╔══════════════════════════════════════════════════╗
║         WASD KEY OVERLAY                         ║
║  Right-click overlay → Control Panel             ║
║  pip install pynput                              ║
╚══════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import colorchooser
import threading, time, json, os, colorsys

try:
    from pynput import keyboard as kb, mouse as ms
    PYNPUT = True
except ImportError:
    PYNPUT = False

# ═══════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════
CFG_PATH = os.path.join(os.path.expanduser("~"), ".wasd_overlay3.json")

DEFAULT = {
    "bg":            "#111d11",
    "bg_opacity":    1.0,
    "key_off":       "#1e3a1e",
    "key_on":        "#39ff14",
    "txt_off":       "#7abf7a",
    "txt_on":        "#0a0a0a",
    "border":        "#2e5c2e",
    "rainbow":       False,
    "rainbow_speed": 3,
    "cell":          56,
    "gap":           4,
    "radius":        7,
    "opacity":       0.90,
    "always_top":    True,
    "show_wasd":     True,
    "show_arrows":   False,
    "show_lmb":      True,
    "show_mmb":      False,
    "show_rmb":      True,
    "show_cps":      True,
    "show_space":    False,
    "show_shift":    False,
    "show_ctrl":     False,
    "show_jump":     False,
    "show_sneak":    False,
    "lbl_w":  "W",   "lbl_a": "A",   "lbl_s": "S",   "lbl_d": "D",
    "lbl_up": "UP",  "lbl_dn":"DN",  "lbl_lt":"LT",  "lbl_rt":"RT",
    "lbl_sp": "SPC", "lbl_sh":"SHF", "lbl_ct":"CTL",
    "lbl_j":  "J",   "lbl_c": "C",
    "lbl_lmb":"LMB", "lbl_mmb":"MMB","lbl_rmb":"RMB",
    "font_fam":  "Courier",
    "font_sz":   13,
    "font_bold": True,
    "x": 120, "y": 120,
}

TRANS = "#010101"   # treated as transparent


def load_cfg():
    if os.path.exists(CFG_PATH):
        try:
            with open(CFG_PATH) as f:
                d = json.load(f)
            out = DEFAULT.copy(); out.update(d)
            return out
        except Exception:
            pass
    return DEFAULT.copy()


def save_cfg(c):
    try:
        with open(CFG_PATH, "w") as f:
            json.dump(c, f, indent=2)
    except Exception:
        pass


# ═══════════════════════════════════════════════════
#  CPS counter
# ═══════════════════════════════════════════════════
class CPS:
    def __init__(self):
        self._t = []; self._lk = threading.Lock()
    def hit(self):
        with self._lk: self._t.append(time.time())
    def get(self):
        now = time.time()
        with self._lk:
            self._t = [t for t in self._t if now-t <= 1.0]
            return len(self._t)


# ═══════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════
def blend(hexcol, alpha):
    def p(h):
        h = h.lstrip("#")
        return int(h[:2],16), int(h[2:4],16), int(h[4:],16)
    r1,g1,b1 = p(hexcol)
    r2,g2,b2 = p(TRANS)
    r = int(r1*alpha + r2*(1-alpha))
    g = int(g1*alpha + g2*(1-alpha))
    b = int(b1*alpha + b2*(1-alpha))
    if (r,g,b)==(1,1,1): r=2
    return "#{:02x}{:02x}{:02x}".format(r,g,b)


def contrast(hexcol):
    h = hexcol.lstrip("#")
    r,g,b = int(h[:2],16),int(h[2:4],16),int(h[4:],16)
    return "#000000" if 0.299*r+0.587*g+0.114*b>128 else "#ffffff"


def rrect(cv, x1, y1, x2, y2, r, **kw):
    r = max(1, min(r,(x2-x1)//2,(y2-y1)//2))
    pts = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
           x2,y2-r, x2,y2, x2-r,y2, x1+r,y2,
           x1,y2, x1,y2-r, x1,y1+r, x1,y1]
    return cv.create_polygon(pts, smooth=True, **kw)


# ═══════════════════════════════════════════════════
#  OVERLAY
# ═══════════════════════════════════════════════════
class Overlay:
    def __init__(self, root, cfg):
        self.root=root; self.cfg=cfg
        self._hue=0.0; self._panel=None
        self.keys={k:False for k in
                   ["w","a","s","d","up","down","left","right",
                    "space","shift","ctrl","j","c"]}
        self.lmb=False; self.rmb=False; self.mmb=False
        self.lmb_c=CPS(); self.rmb_c=CPS(); self.mmb_c=CPS()
        self._dx=0; self._dy=0
        self._setup(); self._start_listeners(); self._tick()

    def _setup(self):
        r=self.root
        r.overrideredirect(True)
        r.attributes("-topmost", self.cfg["always_top"])
        r.attributes("-alpha",   self.cfg["opacity"])
        r.attributes("-transparentcolor", TRANS)
        r.configure(bg=TRANS)
        r.geometry(f"+{self.cfg['x']}+{self.cfg['y']}")
        self.cv=tk.Canvas(r, bg=TRANS, highlightthickness=0)
        self.cv.pack(fill=tk.BOTH, expand=True)
        self.cv.bind("<ButtonPress-1>",   self._ds)
        self.cv.bind("<B1-Motion>",       self._dm)
        self.cv.bind("<ButtonPress-3>",   self._open_panel)
        self.cv.bind("<Double-Button-1>", self._open_panel)

    def _sections(self):
        c=self.cfg; secs=[]
        if c["show_wasd"]:   secs+=["w_row","asd_row"]
        if c["show_arrows"]: secs+=["up_row","arrow_row"]
        ex=[k for k,ck in [("shift","show_shift"),("ctrl","show_ctrl"),
                             ("space","show_space"),("j","show_jump"),
                             ("c","show_sneak")] if c[ck]]
        if ex: secs.append(("extras",ex))
        btns=[(c["lbl_lmb"],"lmb",0.70),(c["lbl_mmb"],"mmb",0.80),(c["lbl_rmb"],"rmb",0.90)]
        vis=[(l,k,h) for l,k,h in btns if c[f"show_{k}"]]
        if vis: secs.append(("mouse",vis))
        return secs

    def _dims(self):
        c=self.cfg; cs=c["cell"]; gap=c["gap"]; pad=10
        secs=self._sections(); nr=len(secs)
        w=cs*3+gap*2+pad*2
        h=cs*nr+gap*(nr-1)+pad*2 if nr else pad*2
        return w,h,pad,cs,gap,secs

    def _rb(self, off=0.0, s=1.0, v=1.0):
        h=(self._hue+off)%1.0
        r,g,b=colorsys.hsv_to_rgb(h,s,v)
        return "#{:02x}{:02x}{:02x}".format(int(r*255),int(g*255),int(b*255))

    def _draw(self):
        c=self.cfg; w,h,pad,cs,gap,secs=self._dims()
        self.root.geometry(f"{w}x{h}")
        self.cv.config(width=w, height=h)
        self.cv.delete("all")

        bga=c.get("bg_opacity",1.0)
        if bga>0.01:
            rrect(self.cv,2,2,w-2,h-2,c["radius"]+3,
                  fill=blend(c["bg"],bga), outline=blend(c["border"],min(bga+0.3,1.0)), width=1)

        fn =(c["font_fam"],c["font_sz"],"bold" if c["font_bold"] else "normal")
        fns=(c["font_fam"],max(7,c["font_sz"]-5),"normal")
        rb=c["rainbow"]

        def cc(col,ri,ww=1):
            x1=pad+col*(cs+gap); y1=pad+ri*(cs+gap)
            return x1,y1,x1+cs*ww+gap*(ww-1),y1+cs

        def kc(active,off):
            if rb and active:
                bg=self._rb(off); fg=contrast(bg)
            elif rb:
                bg=self._rb(off,0.6,0.3); fg=c["txt_off"]
            else:
                bg=c["key_on"] if active else c["key_off"]
                fg=c["txt_on"] if active else c["txt_off"]
            return bg,fg

        def dk(col,ri,lbl,active,ww=1,off=0.0):
            x1,y1,x2,y2=cc(col,ri,ww); bg,fg=kc(active,off)
            rrect(self.cv,x1,y1,x2,y2,c["radius"],fill=bg,outline=c["border"],width=1)
            self.cv.create_text((x1+x2)//2,(y1+y2)//2,text=lbl,fill=fg,font=fn)

        def dm(col,ri,lbl,cps_val,active,ww=1,off=0.0):
            x1,y1,x2,y2=cc(col,ri,ww); bg,fg=kc(active,off)
            rrect(self.cv,x1,y1,x2,y2,c["radius"],fill=bg,outline=c["border"],width=1)
            cx=(x1+x2)//2
            self.cv.create_text(cx,y1+cs//3,text=lbl,fill=fg,font=fn)
            if c["show_cps"]:
                self.cv.create_text(cx,y1+cs*2//3+3,text=f"{cps_val} CPS",fill=fg,font=fns)
            self.cv.create_line(x1+6,y2-10,x2-6,y2-10,fill=c["border"],width=1)

        ks=self.keys; L=c
        LM={"shift":L["lbl_sh"],"ctrl":L["lbl_ct"],"space":L["lbl_sp"],
            "j":L["lbl_j"],"c":L["lbl_c"]}
        SM={"shift":"shift","ctrl":"ctrl","space":"space","j":"j","c":"c"}

        for ri,sec in enumerate(secs):
            if sec=="w_row":    dk(1,ri,L["lbl_w"],ks["w"])
            elif sec=="asd_row":
                dk(0,ri,L["lbl_a"],ks["a"],off=0.10)
                dk(1,ri,L["lbl_s"],ks["s"],off=0.20)
                dk(2,ri,L["lbl_d"],ks["d"],off=0.30)
            elif sec=="up_row": dk(1,ri,L["lbl_up"],ks["up"],off=0.40)
            elif sec=="arrow_row":
                dk(0,ri,L["lbl_lt"],ks["left"], off=0.45)
                dk(1,ri,L["lbl_dn"],ks["down"], off=0.50)
                dk(2,ri,L["lbl_rt"],ks["right"],off=0.55)
            elif isinstance(sec,tuple) and sec[0]=="extras":
                items=sec[1]; n=len(items)
                if n==1:   dk(0,ri,LM[items[0]],ks.get(SM.get(items[0],""),False),ww=3,off=0.60)
                elif n==2:
                    dk(0,ri,LM[items[0]],ks.get(SM.get(items[0],""),False),off=0.60)
                    dk(1,ri,LM[items[1]],ks.get(SM.get(items[1],""),False),ww=2,off=0.65)
                else:
                    for ci,it in enumerate(items[:3]):
                        dk(ci,ri,LM.get(it,it),ks.get(SM.get(it,it),False),off=0.60+ci*0.05)
            elif isinstance(sec,tuple) and sec[0]=="mouse":
                btns=sec[1]; n=len(btns)
                if n==1:
                    l2,bk,ho=btns[0]
                    dm(0,ri,l2,getattr(self,f"{bk}_c").get(),getattr(self,bk),ww=3,off=ho)
                elif n==2:
                    l2,bk,ho=btns[0]; dm(0,ri,l2,getattr(self,f"{bk}_c").get(),getattr(self,bk),ww=2,off=ho)
                    l2,bk,ho=btns[1]; dm(2,ri,l2,getattr(self,f"{bk}_c").get(),getattr(self,bk),off=ho)
                else:
                    for ci,(l2,bk,ho) in enumerate(btns[:3]):
                        dm(ci,ri,l2,getattr(self,f"{bk}_c").get(),getattr(self,bk),off=ho)

    def _tick(self):
        self._hue=(self._hue+self.cfg.get("rainbow_speed",3)*0.002)%1.0
        self._draw()
        self.root.after(50,self._tick)

    def _start_listeners(self):
        if not PYNPUT: return
        KM={kb.Key.space:"space",kb.Key.shift:"shift",kb.Key.shift_r:"shift",
            kb.Key.ctrl_l:"ctrl",kb.Key.ctrl_r:"ctrl",
            kb.Key.up:"up",kb.Key.down:"down",kb.Key.left:"left",kb.Key.right:"right"}
        def on_p(key):
            try:
                ch=key.char.lower() if hasattr(key,"char") and key.char else None
                if ch and ch in self.keys: self.keys[ch]=True
            except: pass
            if key in KM: self.keys[KM[key]]=True
        def on_r(key):
            try:
                ch=key.char.lower() if hasattr(key,"char") and key.char else None
                if ch and ch in self.keys: self.keys[ch]=False
            except: pass
            if key in KM: self.keys[KM[key]]=False
        def on_c(x,y,btn,pressed):
            if btn==ms.Button.left:
                self.lmb=pressed
                if pressed: self.lmb_c.hit()
            elif btn==ms.Button.right:
                self.rmb=pressed
                if pressed: self.rmb_c.hit()
            elif btn==ms.Button.middle:
                self.mmb=pressed
                if pressed: self.mmb_c.hit()
        threading.Thread(target=lambda:kb.Listener(on_press=on_p,on_release=on_r).start(),daemon=True).start()
        threading.Thread(target=lambda:ms.Listener(on_click=on_c).start(),daemon=True).start()

    def _ds(self,e): self._dx=e.x_root-self.root.winfo_x(); self._dy=e.y_root-self.root.winfo_y()
    def _dm(self,e):
        x=e.x_root-self._dx; y=e.y_root-self._dy
        self.root.geometry(f"+{x}+{y}"); self.cfg["x"]=x; self.cfg["y"]=y
    def _open_panel(self,e=None):
        if self._panel and self._panel.winfo_exists(): self._panel.lift(); return
        self._panel=ControlPanel(self.root,self.cfg,self._apply)
    def _apply(self,nc):
        self.cfg.update(nc)
        self.root.attributes("-topmost",self.cfg["always_top"])
        self.root.attributes("-alpha",  self.cfg["opacity"])
        save_cfg(self.cfg)


# ═══════════════════════════════════════════════════
#  CONTROL PANEL
# ═══════════════════════════════════════════════════
BG="#131313"; BG2="#1c1c1c"; BG3="#242424"
ACC="#39ff14"; ACC2="#1a7a00"
FG="#e0e0e0"; FG2="#888888"; RED="#ff4444"
FONT=("Consolas",10); FONTB=("Consolas",10,"bold")

class ControlPanel:
    def __init__(self,parent,cfg,on_apply):
        self.cfg=cfg.copy(); self.on_apply=on_apply
        self._sw={}; self._cv={}
        self.win=tk.Toplevel(parent)
        self.win.title("WASD Overlay — Control Panel")
        self.win.configure(bg=BG)
        self.win.resizable(True,True)
        self.win.minsize(480,560)
        self.win.geometry("510x660")
        self._build()

    def _build(self):
        w=self.win
        # header
        hdr=tk.Frame(w,bg="#0d0d0d",pady=10); hdr.pack(fill=tk.X)
        tk.Label(hdr,text="⬛ WASD OVERLAY",font=("Consolas",14,"bold"),
                 bg="#0d0d0d",fg=ACC).pack(side=tk.LEFT,padx=14)
        tk.Label(hdr,text="right-click overlay to reopen",font=("Consolas",8),
                 bg="#0d0d0d",fg=FG2).pack(side=tk.RIGHT,padx=14)
        # scrollable area
        body=tk.Frame(w,bg=BG); body.pack(fill=tk.BOTH,expand=True)
        self._cnv=tk.Canvas(body,bg=BG,highlightthickness=0)
        sb=tk.Scrollbar(body,orient="vertical",command=self._cnv.yview)
        self._cnv.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT,fill=tk.Y)
        self._cnv.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        self._sf=tk.Frame(self._cnv,bg=BG)
        self._wid=self._cnv.create_window((0,0),window=self._sf,anchor="nw")
        self._sf.bind("<Configure>",lambda e:self._cnv.configure(scrollregion=self._cnv.bbox("all")))
        self._cnv.bind("<Configure>",lambda e:self._cnv.itemconfig(self._wid,width=e.width))
        # bind scroll on all widgets recursively via bind_all on canvas
        self._cnv.bind_all("<MouseWheel>",self._scroll)
        # sections
        f=self._sf
        self._sec(f,"🎨  COLOURS");       self._colours(f)
        self._sec(f,"🌈  RAINBOW");        self._rainbow(f)
        self._sec(f,"🔲  KEYS & BUTTONS"); self._toggles(f)
        self._sec(f,"🖱️  MOUSE LABELS");   self._mouse_labels(f)
        self._sec(f,"🏷️  KEY LABELS");     self._key_labels(f)
        self._sec(f,"📐  SIZE & SHAPE");   self._sizes(f)
        self._sec(f,"🔤  FONT");           self._font(f)
        self._sec(f,"🖥️  WINDOW");         self._window(f)
        # footer
        foot=tk.Frame(w,bg="#0d0d0d",pady=8); foot.pack(fill=tk.X)
        self._b(foot,"✅ Apply",     self._apply,   ACC2,   ACC    ).pack(side=tk.RIGHT,padx=8)
        self._b(foot,"❌ Close",     self.win.destroy,"#3a0000",RED).pack(side=tk.RIGHT)
        self._b(foot,"🔄 Reset",     self._reset,   "#222", FG2    ).pack(side=tk.LEFT,padx=8)
        self._b(foot,"💾 Save+Apply",self._save,    "#002244","#44aaff").pack(side=tk.LEFT)

    def _scroll(self,e): self._cnv.yview_scroll(int(-1*(e.delta/120)),"units")
    def _sec(self,p,t):
        fr=tk.Frame(p,bg=BG); fr.pack(fill=tk.X,pady=(10,0))
        tk.Frame(fr,bg=ACC2,height=2).pack(fill=tk.X)
        tk.Label(fr,text=t,font=FONTB,bg=BG,fg=ACC,anchor="w",padx=12,pady=4).pack(fill=tk.X)
    def _card(self,p):
        f=tk.Frame(p,bg=BG2,padx=12,pady=8); f.pack(fill=tk.X,padx=12,pady=4); return f
    def _b(self,p,t,cmd,bg,fg):
        return tk.Button(p,text=t,command=cmd,bg=bg,fg=fg,font=FONTB,
                         relief=tk.FLAT,padx=10,pady=6,cursor="hand2")
    def _sld(self,p,lbl,key,lo,hi,res=1,typ=float):
        r=tk.Frame(p,bg=BG2); r.pack(fill=tk.X,pady=3)
        tk.Label(r,text=f"{lbl:<20}",font=FONT,bg=BG2,fg=FG,width=20,anchor="w").pack(side=tk.LEFT)
        var=tk.DoubleVar(value=self.cfg[key])
        def u(v): self.cfg[key]=typ(float(v))
        tk.Scale(r,from_=lo,to=hi,resolution=res,orient=tk.HORIZONTAL,
                 variable=var,command=u,bg=BG2,fg=FG,troughcolor=BG3,
                 highlightthickness=0,length=210,showvalue=True,
                 activebackground=ACC).pack(side=tk.LEFT)

    def _colours(self,p):
        f=self._card(p)
        items=[("Background","bg"),("Key (off)","key_off"),("Key (active)","key_on"),
               ("Text (off)","txt_off"),("Text (on)","txt_on"),("Border","border")]
        presets=[
            ("🟢 MC",    "#111d11","#1e3a1e","#39ff14","#7abf7a","#0a0a0a","#2e5c2e"),
            ("🔵 Ocean", "#0a0f1e","#0d2040","#00cfff","#4499cc","#000a14","#1a4060"),
            ("🔴 Red",   "#1a0000","#3a0000","#ff2222","#cc4444","#0a0000","#660000"),
            ("⚪ Mono",  "#1a1a1a","#2a2a2a","#ffffff","#999999","#000000","#444444"),
            ("🟡 Gold",  "#1a1400","#3a2e00","#ffd700","#aa8800","#0a0800","#5a4500"),
            ("🟣 Purple",  "#120a1e","#2a1040","#cc44ff","#8833cc","#0a0014","#441866"),
            ("🩵 Cyan",  "#001a1a","#003333","#00ffee","#44ccbb","#000a0a","#005555"),
        ]
        pr=tk.Frame(f,bg=BG2); pr.pack(fill=tk.X,pady=(0,8))
        tk.Label(pr,text="Presets:",font=FONT,bg=BG2,fg=FG2).pack(side=tk.LEFT)
        for name,*pc in presets:
            def ap(c=pc):
                ks2=["bg","key_off","key_on","txt_off","txt_on","border"]
                for k,v in zip(ks2,c):
                    self.cfg[k]=v
                    if k in self._sw: self._sw[k].config(bg=v)
                    if k in self._cv: self._cv[k].set(v)
            tk.Button(pr,text=name,command=ap,bg=BG3,fg=FG,font=("Consolas",8),
                      relief=tk.FLAT,padx=4,pady=2,cursor="hand2").pack(side=tk.LEFT,padx=2)

        for lbl,key in items:
            row=tk.Frame(f,bg=BG2); row.pack(fill=tk.X,pady=2)
            tk.Label(row,text=f"{lbl:<22}",font=FONT,bg=BG2,fg=FG,width=22,anchor="w").pack(side=tk.LEFT)
            var=tk.StringVar(value=self.cfg[key]); self._cv[key]=var
            sw=tk.Label(row,bg=self.cfg[key],width=3,relief=tk.SUNKEN,cursor="hand2")
            sw.pack(side=tk.LEFT,padx=6); self._sw[key]=sw
            tk.Entry(row,textvariable=var,width=9,bg=BG3,fg=FG,
                     insertbackground=FG,font=FONT,relief=tk.FLAT).pack(side=tk.LEFT,padx=4)
            def pick(k=key,v=var,s=sw):
                col=colorchooser.askcolor(color=v.get())[1]
                if col: v.set(col); s.config(bg=col); self.cfg[k]=col
            sw.bind("<Button-1>",lambda e,k=key,v=var,s=sw:pick(k,v,s))
            tk.Button(row,text="Pick",command=lambda k=key,v=var,s=sw:pick(k,v,s),
                      bg=BG3,fg=ACC,font=("Consolas",8),relief=tk.FLAT,
                      padx=5,cursor="hand2").pack(side=tk.LEFT)
            def ot(*a,k=key,v=var,s=sw):
                try: s.config(bg=v.get()); self.cfg[k]=v.get()
                except: pass
            var.trace_add("write",ot)

        tk.Frame(f,bg=BG3,height=1).pack(fill=tk.X,pady=8)
        self._sld(f,"Background Opacity","bg_opacity",0.0,1.0,0.05,float)
        tk.Label(f,text="  ↑ 0.0 = transparent bg (keys only shown)",
                 font=("Consolas",8),bg=BG2,fg=FG2,anchor="w").pack(fill=tk.X,pady=(0,2))

    def _rainbow(self,p):
        f=self._card(p)
        rv=tk.BooleanVar(value=self.cfg["rainbow"])
        def t(): self.cfg["rainbow"]=rv.get()
        tk.Checkbutton(f,text="  🌈 Enable Rainbow Mode",variable=rv,command=t,
                       bg=BG2,fg=ACC,activebackground=BG2,activeforeground=ACC,
                       selectcolor=BG3,font=FONTB).pack(anchor="w",pady=2)
        self._sld(f,"Speed","rainbow_speed",1,10,1,int)
        bar=tk.Canvas(f,height=16,bg=BG2,highlightthickness=0)
        bar.pack(fill=tk.X,pady=4)
        def db():
            bar.delete("all"); W=bar.winfo_width() or 460
            for i in range(W):
                r2,g2,b2=colorsys.hsv_to_rgb(i/W,1,1)
                bar.create_line(i,0,i,16,fill="#{:02x}{:02x}{:02x}".format(int(r2*255),int(g2*255),int(b2*255)))
            bar.after(300,db)
        bar.after(400,db)

    def _toggles(self,p):
        f=self._card(p)
        items=[("W A S D","show_wasd"),("Arrow Keys","show_arrows"),
               ("LMB","show_lmb"),("MMB (middle)","show_mmb"),("RMB","show_rmb"),
               ("CPS Counter","show_cps"),("Spacebar","show_space"),
               ("Shift","show_shift"),("Ctrl","show_ctrl"),
               ("J Key","show_jump"),("C Key","show_sneak")]
        cols=3
        for i,(lbl,key) in enumerate(items):
            r2=i//cols; c2=i%cols
            var=tk.BooleanVar(value=self.cfg[key])
            def mk(k=key,v=var):
                def cmd(): self.cfg[k]=v.get()
                return cmd
            tk.Checkbutton(f,text=lbl,variable=var,command=mk(),bg=BG2,fg=FG,
                           activebackground=BG2,activeforeground=ACC,
                           selectcolor=BG3,font=FONT).grid(row=r2,column=c2,sticky="w",padx=10,pady=3)

    def _mouse_labels(self,p):
        f=self._card(p)
        tk.Label(f,text="Text shown on each mouse button:",font=FONT,bg=BG2,fg=FG2).pack(anchor="w",pady=(0,6))
        row=tk.Frame(f,bg=BG2); row.pack(fill=tk.X)
        for name,key in [("LMB","lbl_lmb"),("MMB","lbl_mmb"),("RMB","lbl_rmb")]:
            fr2=tk.Frame(row,bg=BG2); fr2.pack(side=tk.LEFT,padx=12)
            tk.Label(fr2,text=name+":",font=FONT,bg=BG2,fg=FG2).pack(side=tk.LEFT)
            var=tk.StringVar(value=self.cfg[key])
            def oc(*a,k=key,v=var): self.cfg[k]=v.get()
            var.trace_add("write",oc)
            tk.Entry(fr2,textvariable=var,width=6,bg=BG3,fg=ACC,
                     insertbackground=ACC,font=FONTB,relief=tk.FLAT).pack(side=tk.LEFT,padx=4)

    def _key_labels(self,p):
        f=self._card(p)
        items=[("W","lbl_w"),("A","lbl_a"),("S","lbl_s"),("D","lbl_d"),
               ("↑","lbl_up"),("↓","lbl_dn"),("←","lbl_lt"),("→","lbl_rt"),
               ("Space","lbl_sp"),("Shift","lbl_sh"),("Ctrl","lbl_ct"),
               ("J","lbl_j"),("C","lbl_c")]
        for i,(lbl,key) in enumerate(items):
            fr2=tk.Frame(f,bg=BG2)
            fr2.grid(row=i//4,column=i%4,padx=8,pady=3,sticky="w")
            tk.Label(fr2,text=f"{lbl}:",font=FONT,bg=BG2,fg=FG2,width=5,anchor="e").pack(side=tk.LEFT)
            var=tk.StringVar(value=self.cfg[key])
            def oc(*a,k=key,v=var): self.cfg[k]=v.get()
            var.trace_add("write",oc)
            tk.Entry(fr2,textvariable=var,width=5,bg=BG3,fg=ACC,
                     insertbackground=ACC,font=FONTB,relief=tk.FLAT).pack(side=tk.LEFT,padx=2)

    def _sizes(self,p):
        f=self._card(p)
        self._sld(f,"Cell Size","cell",30,100,1,int)
        self._sld(f,"Cell Gap","gap",0,20,1,int)
        self._sld(f,"Corner Radius","radius",0,20,1,int)

    def _font(self,p):
        f=self._card(p)
        r1=tk.Frame(f,bg=BG2); r1.pack(fill=tk.X,pady=3)
        tk.Label(r1,text="Family:",font=FONT,bg=BG2,fg=FG,width=10,anchor="w").pack(side=tk.LEFT)
        mono=["Courier","Consolas","Lucida Console","Fixedsys","Terminal","Courier New","OCR A Extended"]
        fv=tk.StringVar(value=self.cfg["font_fam"])
        def off(*a): self.cfg["font_fam"]=fv.get()
        fv.trace_add("write",off)
        om=tk.OptionMenu(r1,fv,*mono)
        om.config(bg=BG3,fg=FG,activebackground=BG2,activeforeground=ACC,
                  relief=tk.FLAT,font=FONT,highlightthickness=0)
        om["menu"].config(bg=BG3,fg=FG,activebackground=ACC2)
        om.pack(side=tk.LEFT,padx=6)
        self._sld(f,"Font Size","font_sz",8,24,1,int)
        r3=tk.Frame(f,bg=BG2); r3.pack(fill=tk.X,pady=3)
        bv=tk.BooleanVar(value=self.cfg["font_bold"])
        def tb(): self.cfg["font_bold"]=bv.get()
        tk.Checkbutton(r3,text="Bold",variable=bv,command=tb,bg=BG2,fg=FG,
                       activebackground=BG2,activeforeground=ACC,
                       selectcolor=BG3,font=FONTB).pack(side=tk.LEFT)

    def _window(self,p):
        f=self._card(p)
        self._sld(f,"Window Opacity","opacity",0.1,1.0,0.05,float)
        r2=tk.Frame(f,bg=BG2); r2.pack(fill=tk.X,pady=3)
        atv=tk.BooleanVar(value=self.cfg["always_top"])
        def t(): self.cfg["always_top"]=atv.get()
        tk.Checkbutton(r2,text="Always on Top",variable=atv,command=t,bg=BG2,fg=FG,
                       activebackground=BG2,activeforeground=ACC,
                       selectcolor=BG3,font=FONTB).pack(side=tk.LEFT)
        r3=tk.Frame(f,bg=BG2); r3.pack(fill=tk.X,pady=6)
        tk.Label(r3,text="Snap to corner:",font=FONT,bg=BG2,fg=FG2).pack(side=tk.LEFT)
        for lbl2,pos in [("↖ TL",(10,10)),("↗ TR",(None,10)),
                          ("↙ BL",(10,None)),("↘ BR",(None,None))]:
            def snap(pp=pos):
                sw=self.win.winfo_screenwidth(); sh=self.win.winfo_screenheight()
                ox,oy=pp
                if ox is None: ox=sw-240
                if oy is None: oy=sh-320
                self.cfg["x"]=ox; self.cfg["y"]=oy
            tk.Button(r3,text=lbl2,command=snap,bg=BG3,fg=FG,font=FONT,
                      relief=tk.FLAT,padx=6,pady=2,cursor="hand2").pack(side=tk.LEFT,padx=4)

    def _apply(self): self.on_apply(self.cfg)
    def _save(self):  save_cfg(self.cfg); self.on_apply(self.cfg)
    def _reset(self):
        self.cfg.update(DEFAULT.copy())
        self.win.destroy()
        ControlPanel(self.win.master,self.cfg,self.on_apply)


# ═══════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════
def main():
    cfg=load_cfg()
    root=tk.Tk(); root.title("WASD Overlay")
    Overlay(root,cfg)
    def on_close(): save_cfg(cfg); root.destroy()
    root.protocol("WM_DELETE_WINDOW",on_close)
    root.mainloop()

if __name__=="__main__":
    main()
