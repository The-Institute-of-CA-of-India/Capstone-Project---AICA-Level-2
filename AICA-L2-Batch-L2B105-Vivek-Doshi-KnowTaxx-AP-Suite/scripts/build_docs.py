"""Build the self-contained docs and presentation: embeds screenshots, OCR results and the QR code.

Edit the sources in docs/src/ and presentation/src/, never the generated files.
Run: python scripts/build_docs.py --repo-url https://github.com/you/knowtaxx-ap-suite
The QR code needs: pip install qrcode
"""
import argparse
import base64
import io
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screenshots"
DEFAULT_REPO = ("https://github.com/The-Institute-of-CA-of-India/Capstone-Project---AICA-Level-2"
                "/tree/main/AICA-L2-Batch-L2B105-Vivek-Doshi-KnowTaxx-AP-Suite")
PAGES = [(ROOT / "docs/src/User_Guide.src.html", ROOT / "docs/User_Guide.html"),
         (ROOT / "docs/src/Quick_Start.src.html", ROOT / "docs/Quick_Start.html"),
         (ROOT / "presentation/src/Capstone_Presentation.src.html", ROOT / "presentation/Capstone_Presentation.html")]
_cache = {}


def embed(match):
    name = match.group(1)
    if name not in _cache:
        image = Image.open(SHOTS / f"{name}.png").convert("RGB")
        if image.width > 1280:
            image = image.resize((1280, int(image.height * 1280 / image.width)), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=80, optimize=True)
        _cache[name] = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()
    return f'src="{_cache[name]}"'


def qr_svg(url):
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        print("qrcode is not installed: the slide shows the link only.")
        return ""
    image = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buffer = io.BytesIO()
    image.save(buffer)
    return re.sub(r"<\?xml.*?\?>", "", buffer.getvalue().decode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-url", default=DEFAULT_REPO)
    args = parser.parse_args()
    report = json.loads((ROOT / "docs" / "ocr_benchmark.json").read_text(encoding="utf-8"))
    tokens = {"{{REPO_URL}}": args.repo_url, "{{QR_SVG}}": qr_svg(args.repo_url),
              "{{OCR_CLEAN}}": f"{report['clean']['field_accuracy']:.1%}",
              "{{OCR_PHOTO}}": f"{report['degraded_photo']['field_accuracy']:.1%}",
              "{{OCR_DOCS}}": str(report["clean"]["documents"])}
    for source, target in PAGES:
        html = source.read_text(encoding="utf-8")
        for token, value in tokens.items():
            html = html.replace(token, value)
        html = re.sub(r'src="(?:\.\./)*(?:docs/)?screenshots/([\w-]+)\.png"', embed, html)
        target.write_text(html, encoding="utf-8")
        print(f"{target.relative_to(ROOT)}: {target.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
