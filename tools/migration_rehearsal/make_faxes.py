import json, os, sys
from PIL import Image, ImageDraw
root = sys.argv[1]
faxes = [
    # day, hylaid, number, modem, pages, numid (known company number), time
    ("2026:09:28", "1001", "+82-2-5550200", "ttyS0", 2, 3, "09:15:02"),
    ("2026:09:28", "1002", "+49-30-5550101", "ttyS0", 1, 2, "10:20:11"),
    ("2026:09:29", "1003", "+1-555-0100", "ttyS1", 3, 4, "11:45:30"),
    ("2026:09:29", "1004", "+33-1-555-0123", "ttyS1", 1, 0, "13:05:44"),
    ("2026:09:30", "1005", "+82-2-5550200", "ttyS0", 2, 3, "08:00:05"),
    ("2026:10:01", "1006", "+49-30-5550102", "ttyS0", 1, 0, "16:30:59"),
]
out = []
for day, jid, number, modem, pages, numid, hour in faxes:
    clean = "".join(c for c in number if c.isdigit())
    rel = f"/faxes/recvd/{day.replace(':','/')}/{clean}/{jid}"
    folder = root + rel
    os.makedirs(folder, exist_ok=True)
    frames = []
    for p in range(pages):
        im = Image.new("1", (1728, 2200), 1); d = ImageDraw.Draw(im)
        for y in range(120, 2000, 50):
            d.text((120, y), f"fax {jid} page {p+1} from {number} " * 2, fill=0)
        frames.append(im)
    frames[0].save(f"{folder}/fax.tif", save_all=True, append_images=frames[1:], compression="group4", dpi=(204, 196))
    frames[0].save(f"{folder}/fax.pdf", save_all=True, append_images=frames[1:], format="PDF", resolution=204)
    thumb = frames[0].convert("L").resize((80, 104)); thumb.convert("P").save(f"{folder}/thumb.gif")
    for p in range(pages):
        frames[p].convert("L").resize((320, 414)).convert("P").save(f"{folder}/prev{p}.gif")
    out.append(dict(path=rel, numid=numid, number=number, modem=modem, pages=pages, date=day.replace(":", "-") + " " + hour))
json.dump(out, open(root + "/faxes_to_register.json", "w"))
print(len(out), "fax folders made")
