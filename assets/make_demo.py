#!/usr/bin/env python3
"""Animated GIF for lying-spreadsheets. Terminal output is REAL output from
sheetguard.py on the bundled clean/poisoned fixtures."""
from PIL import Image, ImageDraw, ImageFont
import os
W,H=1200,700
BG=(13,17,23); FG=(201,209,217); MUT=(139,148,158); GRN=(63,185,80)
CYN=(88,166,255); YEL=(210,153,34); RED=(248,81,73); CHROME=(22,27,34)
MENLO="/System/Library/Fonts/Menlo.ttc"; ARIALB="/System/Library/Fonts/Supplemental/Arial Bold.ttf"; ARIAL="/System/Library/Fonts/Supplemental/Arial.ttf"
def f(p,s,i=0):
    try: return ImageFont.truetype(p,s,index=i)
    except Exception: return ImageFont.truetype(p,s)
mono=f(MENLO,20); mono_s=f(MENLO,17); title=f(ARIALB,44); subt=f(ARIAL,24); small=f(ARIAL,18)
frames=[]; durations=[]
def base():
    img=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(img)
    d.rectangle([0,0,W,44],fill=CHROME)
    for i,c in enumerate([(255,95,86),(255,189,46),(39,201,63)]): d.ellipse([22+i*26,15,36+i*26,29],fill=c)
    return img,d
def wt(d,t): w=d.textlength(t,font=mono_s); d.text(((W-w)/2,14),t,font=mono_s,fill=MUT)
def add(img,ms): frames.append(img.convert("P",palette=Image.ADAPTIVE,colors=128)); durations.append(ms)
def card(lines,ms=1600,tt="lying-spreadsheets"):
    img,d=base(); wt(d,tt); total=sum(h for *_,h in lines); y=(H+44-total)/2
    for text,fnt,col,lh in lines:
        w=d.textlength(text,font=fnt); d.text(((W-w)/2,y),text,font=fnt,fill=col); y+=lh
    add(img,ms)
def term(tt,lines,typing=None,cursor=True,y0=68):
    img,d=base(); wt(d,tt); y=y0
    for text,col in lines: d.text((40,y),text,font=mono,fill=col); y+=29
    if typing is not None:
        text,col=typing; d.text((40,y),text,font=mono,fill=col)
        if cursor:
            cx=40+d.textlength(text,font=mono); d.rectangle([cx+2,y+3,cx+12,y+24],fill=FG)
    return img
def type_line(tt,prev,prefix,body,col,step=3,ms=24,y0=68):
    i=0
    while i<=len(body): add(term(tt,prev,typing=(prefix+body[:i],col),y0=y0),ms); i+=step
    add(term(tt,prev,typing=(prefix+body,col),cursor=False,y0=y0),250)
def reveal(tt,head,out,hold=1500):
    acc=list(head)
    for ln in out: acc.append(ln); add(term(tt,acc,cursor=False),200)
    add(term(tt,acc,cursor=False),hold); return acc

# A title
card([("Lying Spreadsheets",title,FG,66),("XLSX number-format divergence as a parser differential",subt,CYN,48),
      ("",subt,FG,16),("github.com/legalrealist/lying-spreadsheets",small,MUT,30)],1600)
# B problem
card([("A cell displays      $127,400,000",subt,FG,52),
      ("openpyxl / pandas read   146500000",subt,RED,52),
      ("",subt,FG,16),
      ("The number format is a hardcoded string that lies about the raw value.",small,MUT,30)],2300)
# C quickstart + clean
T="zsh — lying-spreadsheets"
type_line(T,[],"$ ","python3 generate_xlsx.py        # clean + poisoned XLSX",FG,step=4,ms=20)
h=[("$ python3 generate_xlsx.py        # clean + poisoned XLSX",FG)]
type_line(T,h,"$ ","python3 sheetguard.py examples/financials_clean.xlsx",FG,step=4,ms=20)
h=[("$ python3 generate_xlsx.py        # clean + poisoned XLSX",FG),
   ("$ python3 sheetguard.py examples/financials_clean.xlsx",FG)]
add(term(T,h,cursor=False),350)
h+=[("--- financials_clean.xlsx: [CLEAN] 0 critical, 0 warning ---",GRN)]
add(term(T,h,cursor=False),1400)
# D poisoned scan (real)
type_line(T,[],"$ ","python3 sheetguard.py examples/financials_poisoned.xlsx",FG,step=4,ms=20)
hp=[("$ python3 sheetguard.py examples/financials_poisoned.xlsx",FG)]
reveal(T,hp,[
 ("--- financials_poisoned.xlsx: [CRITICAL] 27 critical, 3 warning ---",RED),
 ("",FG),
 ("  B13  Static format divergence:",FG),
 ("       displays '$127,400,000'  but raw value is 146500000.0",FG),
 ("  B15  displays '$29,200,000'   but raw value is 48700000.0",FG),
 ("  ...  28 more findings across the sheet",MUT),
], hold=1900)
# E end
card([("sheetguard flags every cell where the format string ≠ the raw value",subt,FG,48),
      ("the original lying-spreadsheets · see also lying-spreadsheets-ii",small,MUT,40),
      ("",subt,FG,12),
      ("github.com/legalrealist/lying-spreadsheets",small,CYN,30)],2300)

out=os.path.join(os.path.dirname(__file__),"demo.gif")
frames[0].save(out,save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=True,disposal=2)
print(f"wrote {out} ({len(frames)} frames, {os.path.getsize(out)//1024} KB)")
