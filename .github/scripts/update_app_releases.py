#!/usr/bin/env python3
"""Refresh the release facts embedded in apps/index.html.

Each app on the downloads page is backed by a GitHub Release asset. This
rewrites the version, size, publish date, SHA-256 and download URL for each
one, leaving the hand-written copy (name, icon, description, features)
untouched. Run by .github/workflows/update-app-releases.yml.

Three ways of tracking "latest" are supported per app:

  fixed_tag   the release tag never changes and the asset is replaced in
              place, so the download URL is already permanent
  tag_prefix  one repo publishes several products; the newest release whose
              tag starts with the prefix wins
  (neither)   plain newest release in the repo

The asset is matched by exact name, or by `asset_re` when the filename
carries the version and therefore changes every release.

Nothing is written unless every app resolved, so a transient API failure
cannot blank out the page.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

PAGE = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), 'apps', 'index.html')

# app id -> where its release lives and which asset to link
SOURCES = {
    'cubevpn-android': {
        'repo': 'cubepy/CubeVPN',
        # the 64-bit build: what nearly every current phone wants, and a
        # third of the size of the universal APK
        'asset_re': r'^CubeVPN-v[\d.]+-arm64-v8a-release\.apk$',
    },
    'cubewin': {
        'repo': 'cubepy/CubeWin',
        'asset': 'CubeVPN-windows-x64.zip',
    },
    'sms-forwarder': {
        # cubepy/cubepay-android is private, so the public download is the
        # copy republished under a fixed tag on the docs repo
        'repo': 'cubepy/cubepay-doc',
        'fixed_tag': 'android-latest',
        'asset': 'CubePay.apk',
    },
    'wordpress': {
        'repo': 'cubepy/cubepay-doc',
        'tag_prefix': 'wp-',
        'asset': 'smspay-gateway.zip',
    },
}


def api(repo, path):
    req = urllib.request.Request(
        f'https://api.github.com/repos/{repo}{path}',
        headers={'Accept': 'application/vnd.github+json',
                 'User-Agent': 'cube-apps-refresh'})
    token = os.environ.get('GH_TOKEN')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def version_from(release):
    """Pull a v1.2.3 out of the tag, falling back to the release name.

    ASCII digits only, and the tag first: these releases are titled in
    Persian ("نسخه ۱.۲.۱"), and \\d would happily match those numerals and
    put them in the version badge.
    """
    for text in (release.get('tag_name') or '', release.get('name') or ''):
        m = re.search(r'v?([0-9]+\.[0-9]+(?:\.[0-9]+)?)', text)
        if m:
            return 'v' + m.group(1)
    return release.get('tag_name') or ''


def resolve(app_id, spec):
    repo = spec['repo']
    if 'fixed_tag' in spec:
        rel = api(repo, '/releases/tags/' + spec['fixed_tag'])
    else:
        prefix = spec.get('tag_prefix', '')
        matching = [r for r in api(repo, '/releases?per_page=100')
                    if not r.get('draft') and not r.get('prerelease')
                    and (r.get('tag_name') or '').startswith(prefix)]
        if not matching:
            raise LookupError(f'{app_id}: no release in {repo} matches '
                              f'{prefix!r}')
        matching.sort(key=lambda r: r.get('published_at') or '', reverse=True)
        rel = matching[0]

    assets = rel.get('assets', [])
    if 'asset_re' in spec:
        pattern = re.compile(spec['asset_re'])
        asset = next((a for a in assets if pattern.match(a.get('name', ''))), None)
        wanted = spec['asset_re']
    else:
        asset = next((a for a in assets if a.get('name') == spec['asset']), None)
        wanted = spec['asset']
    if asset is None:
        raise LookupError(f'{app_id}: no asset matching {wanted!r} in '
                          f'{repo} release {rel.get("tag_name")!r}')

    digest = (asset.get('digest') or '')
    return {
        'url': asset['browser_download_url'],
        'version': version_from(rel),
        'size': asset['size'],
        'updated': (asset.get('updated_at') or rel['published_at'])[:10],
        'sha256': digest.split(':', 1)[1] if digest.startswith('sha256:') else '',
    }


def patch(block, app_id, facts):
    """Replace the four volatile fields of one app entry inside the block."""
    start = block.find(f"id:'{app_id}'")
    if start < 0:
        raise LookupError(f'{app_id}: not present in the APPS block')
    end = block.find('\n  }', start)
    if end < 0:
        raise LookupError(f'{app_id}: malformed entry')
    entry = block[start:end]
    for key, value in facts.items():
        literal = str(value) if key == 'size' else "'%s'" % value
        entry, n = re.subn(rf"(\b{key}:)\s*(?:'[^']*'|\d+)",
                           lambda m: m.group(1) + literal, entry, count=1)
        if not n:
            raise LookupError(f'{app_id}: no {key} field to update')
    return block[:start] + entry + block[end:]


def main():
    html = open(PAGE, encoding='utf-8').read()
    a, b = html.find('/* APPS:START */'), html.find('/* APPS:END */')
    if a < 0 or b < 0:
        sys.exit('APPS markers missing from apps/index.html')

    block = html[a:b]
    try:
        for app_id, spec in SOURCES.items():
            facts = resolve(app_id, spec)
            block = patch(block, app_id, facts)
            print(f'{app_id}: {facts["version"]} '
                  f'({facts["size"]:,} bytes, {facts["updated"]})')
    except (urllib.error.URLError, LookupError, KeyError) as exc:
        sys.exit(f'refresh aborted, page left untouched: {exc}')

    updated = html[:a] + block + html[b:]
    if updated != html:
        open(PAGE, 'w', encoding='utf-8').write(updated)
        print('apps/index.html updated')
    else:
        print('no changes')


if __name__ == '__main__':
    main()
