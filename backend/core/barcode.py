"""Minimal Code 128 (set B) barcode rendered as inline SVG, for item tags."""

PATTERNS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
    "114131", "311141", "411131", "211412", "211214", "211232", "2331112",
]
START_B = 104
STOP = 106


def encode(text):
    """Return the list of symbol values (start, data, checksum, stop)."""
    values = [START_B]
    for ch in text:
        code = ord(ch) - 32
        if not 0 <= code <= 94:
            raise ValueError(f"Character {ch!r} cannot be encoded in Code 128 set B")
        values.append(code)
    checksum = values[0] + sum(i * v for i, v in enumerate(values[1:], start=1))
    values.append(checksum % 103)
    values.append(STOP)
    return values


def svg(text, module=1.4, height=40, quiet=10):
    widths = "".join(PATTERNS[v] for v in encode(text))
    x = quiet
    bars = []
    for i, w in enumerate(widths):
        width = int(w) * module
        if i % 2 == 0:  # even index = bar, odd = space
            bars.append(f'<rect x="{x:.2f}" y="0" width="{width:.2f}" height="{height}"/>')
        x += width
    total = x + quiet
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total:.0f}" height="{height}" '
        f'viewBox="0 0 {total:.2f} {height}" fill="#000">{"".join(bars)}</svg>'
    )
