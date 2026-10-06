"""Generate high-resolution Category Radar macOS AppIcon.icns using Playwright, sips, and iconutil."""
import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from playwright.async_api import async_playwright

SVG_CONTENT = """
<svg width="1024" height="1024" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <!-- Background Gradient -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#090d16"/>
      <stop offset="50%" stop-color="#111827"/>
      <stop offset="100%" stop-color="#1e293b"/>
    </linearGradient>

    <!-- Radar Sweep Gradient -->
    <linearGradient id="sweepGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#00f0ff" stop-opacity="0.45"/>
      <stop offset="60%" stop-color="#2f6fed" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="#2f6fed" stop-opacity="0"/>
    </linearGradient>

    <!-- Glowing filters -->
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <filter id="blipGlow" x="-100%" y="-100%" width="300%" height="300%">
      <feGaussianBlur stdDeviation="6" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.9"/>
      <stop offset="50%" stop-color="#2f6fed" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="#2f6fed" stop-opacity="0"/>
    </radialGradient>

    <!-- Clip squircle -->
    <clipPath id="squircleClip">
      <rect width="1024" height="1024" rx="224" ry="224"/>
    </clipPath>
  </defs>

  <!-- Base Squircle -->
  <rect width="1024" height="1024" rx="224" ry="224" fill="url(#bgGrad)"/>
  <rect width="1020" height="1020" x="2" y="2" rx="222" ry="222" fill="none" stroke="#38bdf8" stroke-width="3" stroke-opacity="0.4"/>

  <!-- Content clipped to squircle -->
  <g clip-path="url(#squircleClip)">
    <!-- Tech Grid Background -->
    <path d="M 112 512 L 912 512 M 512 112 L 512 912" stroke="#1e3a6a" stroke-width="2" stroke-opacity="0.7"/>
    <path d="M 230 230 L 794 794 M 230 794 L 794 230" stroke="#1e3a6a" stroke-width="1.5" stroke-dasharray="8 8" stroke-opacity="0.4"/>

    <!-- Concentric Radar Rings -->
    <circle cx="512" cy="512" r="390" fill="none" stroke="#254784" stroke-width="3" stroke-opacity="0.5"/>
    <circle cx="512" cy="512" r="310" fill="none" stroke="#2b55a1" stroke-width="3.5" stroke-opacity="0.7"/>
    <circle cx="512" cy="512" r="220" fill="none" stroke="#3266c2" stroke-width="4" stroke-opacity="0.85"/>
    <circle cx="512" cy="512" r="130" fill="none" stroke="#3b82f6" stroke-width="4.5"/>
    <circle cx="512" cy="512" r="50" fill="none" stroke="#60a5fa" stroke-width="3.5"/>

    <!-- Distance Ticks -->
    <circle cx="512" cy="512" r="350" fill="none" stroke="#1e3a6a" stroke-width="1.5" stroke-dasharray="4 16" stroke-opacity="0.6"/>

    <!-- Radar Sweep Beam (Pie sector) -->
    <path d="M 512 512 L 770 210 A 390 390 0 0 1 890 410 Z" fill="url(#sweepGrad)"/>
    <!-- Leading Beam Edge -->
    <line x1="512" y1="512" x2="890" y2="410" stroke="#00f0ff" stroke-width="4.5" filter="url(#glow)"/>

    <!-- Ambient Center Radar Halo -->
    <circle cx="512" cy="512" r="90" fill="url(#centerGlow)"/>
    <circle cx="512" cy="512" r="14" fill="#00f0ff" filter="url(#glow)"/>
    <circle cx="512" cy="512" r="6" fill="#ffffff"/>

    <!-- Market Radar Blips with Glowing Pulses -->
    <!-- DE: Germany (Top Right) -->
    <circle cx="680" cy="330" r="20" fill="#f59e0b" fill-opacity="0.25"/>
    <circle cx="680" cy="330" r="12" fill="#fbbf24" filter="url(#blipGlow)"/>
    <circle cx="680" cy="330" r="5" fill="#fff"/>
    <text x="702" y="326" fill="#fde68a" font-family="-apple-system, system-ui, sans-serif" font-size="20" font-weight="800" letter-spacing="1">DE</text>

    <!-- AT: Austria (Right) -->
    <circle cx="730" cy="460" r="18" fill="#ef4444" fill-opacity="0.25"/>
    <circle cx="730" cy="460" r="11" fill="#f87171" filter="url(#blipGlow)"/>
    <circle cx="730" cy="460" r="4.5" fill="#fff"/>
    <text x="750" y="456" fill="#fca5a5" font-family="-apple-system, system-ui, sans-serif" font-size="19" font-weight="800">AT</text>

    <!-- CH: Switzerland (Bottom Right) -->
    <circle cx="640" cy="620" r="18" fill="#ec4899" fill-opacity="0.25"/>
    <circle cx="640" cy="620" r="10" fill="#f472b6" filter="url(#blipGlow)"/>
    <circle cx="640" cy="620" r="4" fill="#fff"/>
    <text x="660" y="618" fill="#fbcfe8" font-family="-apple-system, system-ui, sans-serif" font-size="19" font-weight="800">CH</text>

    <!-- PL: Poland (Top Left) -->
    <circle cx="360" cy="310" r="20" fill="#10b981" fill-opacity="0.25"/>
    <circle cx="360" cy="310" r="12" fill="#34d399" filter="url(#blipGlow)"/>
    <circle cx="360" cy="310" r="5" fill="#fff"/>
    <text x="316" y="306" fill="#a7f3d0" font-family="-apple-system, system-ui, sans-serif" font-size="20" font-weight="800">PL</text>

    <!-- CZ: Czechia (Mid Left) -->
    <circle cx="430" cy="420" r="18" fill="#8b5cf6" fill-opacity="0.25"/>
    <circle cx="430" cy="420" r="11" fill="#a78bfa" filter="url(#blipGlow)"/>
    <circle cx="430" cy="420" r="4.5" fill="#fff"/>
    <text x="388" y="416" fill="#ddd6fe" font-family="-apple-system, system-ui, sans-serif" font-size="19" font-weight="800">CZ</text>

    <!-- HU: Hungary (Bottom Left) -->
    <circle cx="420" cy="640" r="18" fill="#06b6d4" fill-opacity="0.25"/>
    <circle cx="420" cy="640" r="10" fill="#22d3ee" filter="url(#blipGlow)"/>
    <circle cx="420" cy="640" r="4" fill="#fff"/>
    <text x="376" y="638" fill="#a5f3fc" font-family="-apple-system, system-ui, sans-serif" font-size="19" font-weight="800">HU</text>

    <!-- Modern Typography Labels -->
    <text x="512" y="195" text-anchor="middle" fill="#38bdf8" font-family="-apple-system, system-ui, sans-serif" font-size="26" font-weight="800" letter-spacing="9">CATEGORY RADAR</text>
    <text x="512" y="855" text-anchor="middle" fill="#64748b" font-family="-apple-system, system-ui, sans-serif" font-size="18" font-weight="700" letter-spacing="6">CENTRAL EUROPE GTM</text>

    <!-- Subtle Glass Sheen on Top -->
    <path d="M 0 0 L 1024 0 L 1024 380 Q 512 480 0 380 Z" fill="#ffffff" fill-opacity="0.04"/>
  </g>
</svg>
"""

async def build_icns(out_icns: Path):
    temp_dir = Path("data/_icon_build")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    iconset = temp_dir / "radar.iconset"
    iconset.mkdir()

    # 1. Render 1024x1024 PNG with Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1024, "height": 1024})
        html = f"""<!doctype html><html><body style="margin:0;padding:0;overflow:hidden;background:transparent;">{SVG_CONTENT}</body></html>"""
        await page.set_content(html)
        png_1024 = temp_dir / "icon_1024.png"
        await page.screenshot(path=str(png_1024), omit_background=True)
        await browser.close()

    # 2. Downscale into iconset sizes using sips
    sizes = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]

    for name, sz in sizes:
        dst = iconset / name
        subprocess.run(["sips", "-z", str(sz), str(sz), str(png_1024), "--out", str(dst)],
                       check=True, stdout=subprocess.DEVNULL)

    # 3. Compile iconutil
    out_icns.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out_icns)], check=True)
    shutil.rmtree(temp_dir)
    print(f"Generated {out_icns} ({out_icns.stat().st_size} bytes)")

if __name__ == "__main__":
    out_path = Path("assets/AppIcon.icns")
    asyncio.run(build_icns(out_path))
