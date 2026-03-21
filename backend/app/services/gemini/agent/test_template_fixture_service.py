"""
Test template fixture helpers.

Keep fixture file paths and fixture generation logic in one place to avoid
duplicated ad-hoc scripts.
"""

from __future__ import annotations

from pathlib import Path

TEST_TEMPLATE_DIR = Path(__file__).resolve().parent / "test_templates"
ADS_SAMPLE_SPREADSHEET_PATH = TEST_TEMPLATE_DIR / "测试广告数据.xlsx"
LISTING_SAMPLE_SPREADSHEET_PATH = TEST_TEMPLATE_DIR / "测试Listing数据.xlsx"
DATA_ANALYSIS_SAMPLE_SPREADSHEET_PATH = TEST_TEMPLATE_DIR / "测试数据分析数据.xlsx"

_LISTING_HEADERS = ("标题", "五点", "产品描述", "排名")
_LISTING_ROWS = (
    (
        "Boho Layered Anklet Set for Women, 14K Gold Plated Beach Foot Jewelry",
        "1. Lightweight alloy, long-wear comfort | 2. Layered chain design, stacks easily | 3. Adjustable clasp fits most ankles | 4. Tarnish-resistant daily wear finish | 5. Gift-ready pouch included",
        "A 3-piece boho anklet set for summer styling, beach outfits, and daily casual looks. Designed for comfort and easy layering.",
        1245,
    ),
    (
        "Minimalist Pearl Hair Claw Clip, Large Hold for Thick Hair",
        "1. Matte anti-slip teeth | 2. Strong spring for thick hair | 3. Rounded edges reduce pulling | 4. Neutral color for office/casual | 5. Lightweight all-day hold",
        "Large-size claw clip designed for quick styling and secure hold, suitable for medium to thick hair in home, office, and travel use cases.",
        2380,
    ),
    (
        "Silk-Like Square Scarf 27x27 Inch for Handbag, Neck, and Hair Styling",
        "1. Soft satin touch | 2. Double-sided print | 3. Fade-resistant dye | 4. Multi-scene wear options | 5. Machine-washable care",
        "Versatile square scarf for neckwear, hair wrap, handbag decoration, and seasonal outfit matching across commuter and casual settings.",
        1963,
    ),
    (
        "Chunky Resin Hoop Earrings Hypoallergenic Post for Everyday Wear",
        "1. Lightweight resin body | 2. Polished glossy finish | 3. Sensitive-ear friendly post | 4. Secure butterfly back | 5. Minimalist statement size",
        "Modern hoop earrings balancing trend and comfort, tailored for long wear in office, date-night, and weekend outfits.",
        2894,
    ),
    (
        "PU Leather Belt Bag for Women, Adjustable Crossbody Waist Pack",
        "1. Water-resistant outer shell | 2. Adjustable belt/crossbody strap | 3. Multiple zip pockets | 4. Fits phone, keys, cards | 5. Travel-friendly compact body",
        "A compact belt bag for city commuting and short trips, offering organized storage while keeping hands free.",
        1721,
    ),
    (
        "Vintage Oval Sunglasses UV400 for Women Men Retro Street Style",
        "1. UV400 lens protection | 2. Lightweight frame | 3. Comfortable nose pads | 4. Durable hinge construction | 5. Includes cleaning pouch",
        "Retro-inspired oval sunglasses with daily sun protection for driving, travel, and outdoor styling in spring and summer.",
        2117,
    ),
)

_DATA_ANALYSIS_HEADERS = (
    "date",
    "asin",
    "sessions",
    "page_views",
    "units_ordered",
    "ordered_product_sales",
    "ad_spend",
    "ad_sales",
    "acos",
    "rating",
)

_DATA_ANALYSIS_ROWS = (
    ("2026-01-08", "B0AMZ001", 4280, 6512, 236, 8420.5, 1920.8, 7560.2, 0.254, 4.6),
    ("2026-01-09", "B0AMZ001", 4156, 6330, 228, 8149.2, 1861.3, 7022.8, 0.265, 4.6),
    ("2026-01-10", "B0AMZ001", 4028, 6180, 219, 7838.0, 1790.4, 6670.1, 0.268, 4.5),
    ("2026-01-11", "B0AMZ001", 3972, 6041, 211, 7598.3, 1718.9, 6215.7, 0.276, 4.5),
    ("2026-01-12", "B0AMZ002", 3681, 5905, 204, 7224.4, 1644.0, 5740.3, 0.286, 4.4),
    ("2026-01-13", "B0AMZ002", 3790, 6028, 217, 7690.8, 1678.2, 6021.6, 0.279, 4.4),
    ("2026-01-14", "B0AMZ002", 3924, 6188, 225, 8012.6, 1732.5, 6455.9, 0.268, 4.5),
    ("2026-01-15", "B0AMZ003", 4078, 6399, 231, 8297.3, 1810.1, 7019.8, 0.258, 4.5),
    ("2026-01-16", "B0AMZ003", 4210, 6584, 238, 8543.6, 1892.4, 7441.2, 0.254, 4.6),
    ("2026-01-17", "B0AMZ003", 4342, 6771, 246, 8831.0, 1951.6, 7804.9, 0.250, 4.6),
    ("2026-01-18", "B0AMZ004", 4460, 6904, 253, 9116.8, 2018.0, 8267.3, 0.244, 4.7),
    ("2026-01-19", "B0AMZ004", 4586, 7040, 261, 9422.1, 2073.2, 8610.4, 0.241, 4.7),
)


def _write_spreadsheet(
    path: Path,
    *,
    sheet_title: str,
    headers: tuple[str, ...],
    rows: tuple[tuple[object, ...], ...],
    col_widths: dict[str, int],
) -> Path:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_title
    sheet.append(list(headers))
    for row in rows:
        sheet.append(list(row))

    sheet.freeze_panes = "A2"
    for col, width in col_widths.items():
        sheet.column_dimensions[col].width = width

    workbook.save(path)
    return path


def ensure_listing_sample_spreadsheet() -> Path:
    """Create listing fixture spreadsheet when it is missing."""
    TEST_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    if LISTING_SAMPLE_SPREADSHEET_PATH.exists():
        return LISTING_SAMPLE_SPREADSHEET_PATH
    return _write_spreadsheet(
        LISTING_SAMPLE_SPREADSHEET_PATH,
        sheet_title="listing_reference",
        headers=_LISTING_HEADERS,
        rows=_LISTING_ROWS,
        col_widths={"A": 64, "B": 120, "C": 96, "D": 12},
    )


def ensure_data_analysis_sample_spreadsheet() -> Path:
    """Create data-analysis fixture spreadsheet when it is missing."""
    TEST_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    if DATA_ANALYSIS_SAMPLE_SPREADSHEET_PATH.exists():
        return DATA_ANALYSIS_SAMPLE_SPREADSHEET_PATH
    return _write_spreadsheet(
        DATA_ANALYSIS_SAMPLE_SPREADSHEET_PATH,
        sheet_title="analysis_source",
        headers=_DATA_ANALYSIS_HEADERS,
        rows=_DATA_ANALYSIS_ROWS,
        col_widths={
            "A": 14,
            "B": 16,
            "C": 12,
            "D": 12,
            "E": 14,
            "F": 18,
            "G": 12,
            "H": 12,
            "I": 8,
            "J": 8,
        },
    )
