#!/usr/bin/env python3
"""Rebuild the trimmed webfonts under assets/fonts/.

The full Google Fonts subsets ship the whole alphabet each; the landing page
uses a small slice of that. This keeps every glyph the page can render plus a
safety margin (the entire Arabic block and printable ASCII), so ordinary copy
edits do not need a rebuild — only a genuinely new script would.

    pip install fonttools brotli
    python3 tools/subset-fonts.py            # rebuild from assets/fonts/src/
    python3 tools/subset-fonts.py --check    # report sizes, write nothing

Originals live in assets/fonts/src/ and are never modified.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'assets', 'fonts', 'src')
OUT = os.path.join(ROOT, 'assets', 'fonts')
PAGE = os.path.join(ROOT, 'index.html')
FONTS = ['vazirmatn-arabic', 'vazirmatn-latin',
         'spacegrotesk-latin', 'spacegrotesk-latin-ext']


def wanted_codepoints():
    cps = set()
    # Every character present in the page source. This is deliberately a
    # superset: the brand copy shown in the popups lives in JS string
    # literals, so parsing only the markup would miss it.
    with open(PAGE, encoding='utf-8') as fh:
        cps |= {ord(c) for c in fh.read()}
    cps |= set(range(0x20, 0x7F))        # printable ASCII
    # The Persian alphabet in full, rather than the whole Arabic block: the
    # block also carries Arabic-, Urdu- and Sindhi-only letters this site will
    # never set, and they cost about 18 KB.
    cps |= {ord(c) for c in 'آأإئءابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهیةيكؤ'}
    cps |= set(range(0x064B, 0x0653))    # harakat
    cps |= set(range(0x06F0, 0x06FA))    # Persian digits
    cps |= set(range(0x0660, 0x066A))    # Arabic-Indic digits
    cps |= {0x060C, 0x061B, 0x061F, 0x0640, 0x066A, 0x066B, 0x066C, 0x06D4}
    cps |= set(range(0x200C, 0x2010))    # ZWNJ and friends
    cps |= {0x00A0, 0x00B7, 0x00D7, 0x2010, 0x2011, 0x2013, 0x2014,
            0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026,
            0x2190, 0x2191, 0x2192, 0x2193, 0x2197, 0x2715, 0x2713}
    cps.discard(0x0A)
    cps.discard(0x0D)
    return cps


def main():
    check = '--check' in sys.argv
    if not os.path.isdir(SRC):
        sys.exit(f'missing {SRC} — the untrimmed originals must live there')
    unicodes = ','.join('U+%04X' % c for c in sorted(wanted_codepoints()))
    before = after = 0
    for name in FONTS:
        src = os.path.join(SRC, name + '.woff2')
        dst = os.path.join(OUT if not check else '/tmp', name + '.woff2')
        subprocess.run([
            sys.executable, '-m', 'fontTools.subset', src,
            '--unicodes=' + unicodes, '--flavor=woff2',
            '--layout-features=*',      # keep Arabic shaping and kerning
            '--no-hinting', '--desubroutinize',
            '--output-file=' + dst,
        ], check=True, capture_output=True)
        b, a = os.path.getsize(src), os.path.getsize(dst)
        before, after = before + b, after + a
        print(f'{name:26} {b:7,} -> {a:7,}')
    print(f'{"TOTAL":26} {before:7,} -> {after:7,}   '
          f'({before - after:,} bytes saved)')


if __name__ == '__main__':
    main()
