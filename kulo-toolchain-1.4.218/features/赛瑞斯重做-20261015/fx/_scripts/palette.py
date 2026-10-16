WATER=["#061428","#0b2550","#123a73","#1a5296","#2470bd","#2f8fd8","#45adeb","#62c8f5","#8fe0ff","#bdf0ff","#e4fbff","#ffffff"]
RED=["#3a0508","#6a0d14","#a3141f","#d8222c","#ff4a3d","#ff8a7a","#ffc9bf","#ffffff"]
def rgb(h): return tuple(int(h[i:i+2],16) for i in (1,3,5))
if __name__=="__main__":
    from PIL import Image; import base64,io
    for name,P in (("water",WATER),("red",RED)):
        im=Image.new("RGB",(len(P),1))
        for i,c in enumerate(P): im.putpixel((i,0),rgb(c))
        b=io.BytesIO(); im.save(b,"PNG"); s=base64.b64encode(b.getvalue()).decode(); open(f"pal_{name}.b64","w").write(s); print(name,s)
