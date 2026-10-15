#!/usr/bin/env python3
"""施設別受け皿ページ生成(今日どこ行く？ SNS 連携、spec 2026-07-14)。

facilities.json を単一ソースに f/<id>/index.html を全施設分生成する。
- 施設数(公園/無料/プール)は毎回動的算出(テンプレに数字を焼き込まない)
- 分離訴求: 公園と レジャープール(category == "pool")を合算しない
- inactive 施設は「現在休止中」表示で生成(削除しない = シェア済みリンクを 404 にしない)
- 施設一覧 f/index.html と sitemap.xml も同時に生成する(検索エンジンの発見経路、2026-10-16)。
  一覧と sitemap は active 施設だけを載せる(休止中ページは残すが案内しない)
- self-check: 必須キー検証 / 生成件数 = 全施設数 / canonical 数字照合(--expect-*) / OGP・canonical タグ存在
  / 一覧リンク数・sitemap URL 数 = active 施設数(+ トップ・一覧)

使い方(HP repo ルートで):
  python3 scripts/generate-facility-pages.py \
      --facilities ../ParkCompareApp/data/facilities.json \
      --expect-parks 92 --expect-free 55 --expect-pools 20
  (expect 値は docs/app-features-canonical.md の canonical 数字を渡す。
   不一致なら生成せずエラー終了 = canonical doc の更新漏れ検知)
"""
import argparse
import datetime
import html
import json
import pathlib
import sys

APP_STORE_ID = "6762373565"
APP_STORE_URL = f"https://apps.apple.com/jp/app/id{APP_STORE_ID}?pt=128792125&ct=score26_website&mt=8"
SITE_ORIGIN = "https://tosnet-studio.com"
OGP_IMAGE = f"{SITE_ORIGIN}/images/ogp.png"

REQUIRED_KEYS = ("id", "name", "address", "facilityType", "category", "admissionFee", "isActive")

FACILITY_TYPE_LABEL = {
    "outdoor": "屋外",
    "indoor": "屋内",
    "semiOutdoor": "屋内・屋外",
}

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="apple-itunes-app" content="app-id={app_store_id}, app-argument={page_url}">
  <title>{name} | 今日どこ行く？</title>
  <link rel="canonical" href="{page_url}">
  <meta name="description" content="{description}">
  <meta property="og:title" content="{name} | 今日どこ行く？">
  <meta property="og:description" content="{description}">
  <meta property="og:image" content="{ogp_image}">
  <meta property="og:url" content="{page_url}">
  <meta property="og:type" content="article">
  <meta name="twitter:card" content="summary_large_image">
  <!-- generated: {generated_note} -->
  <style>
    body {{ font-family: -apple-system, "Hiragino Sans", sans-serif; margin: 0;
           color: #333; background: #FAFAFA; }}
    .wrap {{ max-width: 560px; margin: 0 auto; padding: 24px 16px; }}
    .card {{ background: #FFF; border-radius: 16px; padding: 24px;
             box-shadow: 0 2px 8px rgba(0,0,0,.06); margin-bottom: 16px; }}
    h1 {{ font-size: 1.4rem; margin: 0 0 8px; }}
    .meta {{ color: #666; font-size: .9rem; margin: 4px 0; }}
    .inactive {{ background: #FFF3E0; color: #BF360C; border-radius: 8px;
                 padding: 8px 12px; font-size: .9rem; margin-top: 12px; }}
    .app {{ text-align: center; }}
    .app h2 {{ font-size: 1.1rem; }}
    .app p {{ font-size: .95rem; line-height: 1.7; }}
    .store {{ display: inline-block; background: #000; color: #FFF; border-radius: 10px;
              padding: 12px 24px; text-decoration: none; font-weight: 600; }}
    footer {{ text-align: center; color: #999; font-size: .8rem; padding: 16px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>{name}</h1>
      <p class="meta">{meta_line}</p>{inactive_notice}
    </div>
    <div class="card app">
      <h2>今日の遊びやすさは、アプリで</h2>
      <p>「今日どこ行く？」は、名古屋近郊の公園・おでかけスポット{parks}施設(うち{free}施設は無料)と
         レジャープール{pools}施設を、雨・UV・風・気温の独自スコアで比較できる無料アプリです。
         この施設の「今日の遊びやすさ」も 10 秒でわかります。</p>
      <a class="store" href="{app_store_url}">App Store で入手(無料)</a>
    </div>
    <footer>tosnet studio ｜ <a href="{site_origin}/">tosnet-studio.com</a></footer>
  </div>
</body>
</html>
"""

LIST_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>収録している施設の一覧 | 今日どこ行く？</title>
  <link rel="canonical" href="{list_url}">
  <meta name="description" content="{description}">
  <meta property="og:title" content="収録している施設の一覧 | 今日どこ行く？">
  <meta property="og:description" content="{description}">
  <meta property="og:image" content="{ogp_image}">
  <meta property="og:url" content="{list_url}">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary_large_image">
  <!-- generated: {generated_note} -->
  <style>
    body {{ font-family: -apple-system, "Hiragino Sans", sans-serif; margin: 0;
           color: #333; background: #FAFAFA; }}
    .wrap {{ max-width: 560px; margin: 0 auto; padding: 24px 16px; }}
    .card {{ background: #FFF; border-radius: 16px; padding: 24px;
             box-shadow: 0 2px 8px rgba(0,0,0,.06); margin-bottom: 16px; }}
    h1 {{ font-size: 1.4rem; margin: 0 0 8px; }}
    h2 {{ font-size: 1.1rem; margin: 0 0 12px; }}
    .lead {{ font-size: .95rem; line-height: 1.7; margin: 0; }}
    ul {{ list-style: none; margin: 0; padding: 0; }}
    li {{ border-top: 1px solid #EEE; }}
    li:first-child {{ border-top: 0; }}
    li a {{ display: flex; justify-content: space-between; gap: 12px; padding: 12px 0;
            color: #333; text-decoration: none; }}
    li a:hover .name {{ text-decoration: underline; }}
    .name {{ font-weight: 600; }}
    .meta {{ color: #666; font-size: .85rem; white-space: nowrap; }}
    .app {{ text-align: center; }}
    .store {{ display: inline-block; background: #000; color: #FFF; border-radius: 10px;
              padding: 12px 24px; text-decoration: none; font-weight: 600; }}
    footer {{ text-align: center; color: #999; font-size: .8rem; padding: 16px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>収録している施設の一覧</h1>
      <p class="lead">アプリ「今日どこ行く？」に収録している、名古屋近郊の公園・おでかけスポット{parks}施設(うち{free}施設は無料)とレジャープール{pools}施設です。施設名から各施設のページを開けます。</p>
    </div>
    <div class="card">
      <h2>公園・おでかけスポット({parks}施設)</h2>
      <ul>
{non_pool_items}
      </ul>
    </div>
    <div class="card">
      <h2>レジャープール({pools}施設)</h2>
      <ul>
{pool_items}
      </ul>
    </div>
    <div class="card app">
      <a class="store" href="{app_store_url}">App Store で入手(無料)</a>
    </div>
    <footer>tosnet studio ｜ <a href="{site_origin}/">tosnet-studio.com</a></footer>
  </div>
</body>
</html>
"""

INACTIVE_NOTICE = (
    '\n      <p class="inactive">この施設は現在休止中です。'
    "最新情報は公式サイトをご確認ください。</p>"
)


def load_facilities(path: pathlib.Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["facilities"] if isinstance(data, dict) else data


def validate_required_keys(facilities: list[dict]) -> str | None:
    """必須キーの欠落を分かりやすいエラー文字列で返す(なければ None)。"""
    for f in facilities:
        missing = [k for k in REQUIRED_KEYS if k not in f]
        if missing:
            return f"施設 {f.get('id', '(id なし)')} に必須キー欠落: {missing}"
    return None


def compute_counts(facilities: list[dict]) -> tuple[int, int, int]:
    """(非プール施設数, 無料施設数, プール数)を算出。プール判定 = category == "pool"、active のみ。

    ⚠️ 非プール 92 は公園 50 + 水族館/動物園/博物館/商業等 42 = 全て公園ではない(D-37)。
    外部コピーの傘表現は「公園・おでかけスポット」。無料も件数(55)= 無料施設で訴求(無料の公園は 43)。
    """
    active = [f for f in facilities if f["isActive"]]
    pools = [f for f in active if f["category"] == "pool"]
    non_pool = [f for f in active if f["category"] != "pool"]
    free_facilities = [f for f in non_pool if f["admissionFee"] == "free"]
    return len(non_pool), len(free_facilities), len(pools)


def render_page(f: dict, parks: int, free: int, pools: int, generated_note: str) -> str:
    type_label = FACILITY_TYPE_LABEL.get(f["facilityType"], "施設")
    # address 未整備の施設が多数あるため空なら括弧・区切りごと省略(2026-07-15 fallback。
    # 一括リサーチで埋まり次第、再生成すれば自動で表示される)
    address = (f.get("address") or "").strip()
    # description は生の値で組み立ててから 1 回だけ escape(二重エスケープ防止)
    address_part = f"({address})" if address else ""
    description_raw = (
        f"{f['name']}{address_part}の今日の遊びやすさを、雨・UV・風・気温の"
        "独自スコアでチェック。名古屋近郊の子連れおでかけ比較アプリ「今日どこ行く？」"
    )
    meta_line = f"{type_label} ｜ {address}" if address else type_label
    return PAGE_TEMPLATE.format(
        name=html.escape(f["name"]),
        meta_line=html.escape(meta_line),
        description=html.escape(description_raw),
        ogp_image=OGP_IMAGE,
        page_url=f"{SITE_ORIGIN}/f/{f['id']}/",
        generated_note=generated_note,
        inactive_notice="" if f["isActive"] else INACTIVE_NOTICE,
        parks=parks,
        free=free,
        pools=pools,
        app_store_url=html.escape(APP_STORE_URL, quote=True),
        app_store_id=APP_STORE_ID,
        site_origin=SITE_ORIGIN,
    )


def render_list_item(f: dict) -> str:
    type_label = FACILITY_TYPE_LABEL.get(f["facilityType"], "施設")
    meta = f"{type_label} ｜ 無料" if f["admissionFee"] == "free" else type_label
    return (
        f'        <li><a href="/f/{html.escape(f["id"], quote=True)}/">'
        f'<span class="name">{html.escape(f["name"])}</span>'
        f'<span class="meta">{html.escape(meta)}</span></a></li>'
    )


def render_list_page(facilities: list[dict], parks: int, free: int, pools: int,
                     generated_note: str) -> str:
    """active 施設だけを、公園・おでかけスポットとレジャープールに分けて並べる(合算しない、D-37)。"""
    active = [f for f in facilities if f["isActive"]]
    non_pool = [f for f in active if f["category"] != "pool"]
    pool = [f for f in active if f["category"] == "pool"]
    description = (
        f"名古屋近郊の公園・おでかけスポット{parks}施設(うち{free}施設は無料)と"
        f"レジャープール{pools}施設の一覧。子連れおでかけ比較アプリ「今日どこ行く？」"
    )
    return LIST_TEMPLATE.format(
        list_url=f"{SITE_ORIGIN}/f/",
        description=html.escape(description),
        ogp_image=OGP_IMAGE,
        generated_note=generated_note,
        parks=parks,
        free=free,
        pools=pools,
        non_pool_items="\n".join(render_list_item(f) for f in non_pool),
        pool_items="\n".join(render_list_item(f) for f in pool),
        app_store_url=html.escape(APP_STORE_URL, quote=True),
        site_origin=SITE_ORIGIN,
    )


def render_sitemap(facilities: list[dict]) -> str:
    """トップ・施設一覧・active 施設ページの URL を列挙する。lastmod は付けない(更新日を持たないため)。"""
    urls = [f"{SITE_ORIGIN}/", f"{SITE_ORIGIN}/f/"]
    urls += [f"{SITE_ORIGIN}/f/{f['id']}/" for f in facilities if f["isActive"]]
    body = "\n".join(f"  <url><loc>{html.escape(u)}</loc></url>" for u in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facilities", required=True, type=pathlib.Path)
    parser.add_argument("--expect-parks", required=True, type=int)
    parser.add_argument("--expect-free", required=True, type=int)
    parser.add_argument("--expect-pools", required=True, type=int)
    parser.add_argument("--out", default="f", type=pathlib.Path)
    parser.add_argument("--sitemap", default="sitemap.xml", type=pathlib.Path)
    args = parser.parse_args()

    facilities = load_facilities(args.facilities)

    # self-check 1: 必須キー(KeyError の生 traceback で落とさない)
    if error := validate_required_keys(facilities):
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    parks, free, pools = compute_counts(facilities)

    # self-check 2: 🚨 canonical 照合ガード(spec §4.2)
    if (parks, free, pools) != (args.expect_parks, args.expect_free, args.expect_pools):
        print(
            f"ERROR: 算出値(公園{parks}/無料{free}/プール{pools})が"
            f" canonical 期待値(公園{args.expect_parks}/無料{args.expect_free}/"
            f"プール{args.expect_pools})と不一致。docs/app-features-canonical.md と"
            " facilities.json のどちらが正か確認してから再実行してください。",
            file=sys.stderr,
        )
        return 1

    generated_note = (
        f"generated {datetime.date.today().isoformat()} from facilities.json"
        f" ({len(facilities)} facilities: parks={parks} free={free} pools={pools})"
    )

    written = 0
    for f in facilities:
        page_dir = args.out / f["id"]
        page_dir.mkdir(parents=True, exist_ok=True)
        html_text = render_page(f, parks, free, pools, generated_note)
        # self-check 3: OGP タグ存在
        for required in ('property="og:title"', 'property="og:image"', 'property="og:url"',
                         f'<link rel="canonical" href="{SITE_ORIGIN}/f/{f["id"]}/">'):
            if required not in html_text:
                print(f"ERROR: {f['id']} の生成 HTML に {required} がない", file=sys.stderr)
                return 1
        (page_dir / "index.html").write_text(html_text, encoding="utf-8")
        written += 1

    # self-check 4: 生成件数 = 全施設数(spec §5)
    if written != len(facilities):
        print(f"ERROR: 生成 {written} 件 ≠ 施設 {len(facilities)} 件", file=sys.stderr)
        return 1

    # 施設一覧と sitemap(active のみ)
    active_count = sum(1 for f in facilities if f["isActive"])
    list_html = render_list_page(facilities, parks, free, pools, generated_note)
    # self-check 5: 一覧のリンク数 = active 施設数
    if list_html.count('<li><a href="/f/') != active_count:
        print("ERROR: 施設一覧のリンク数が active 施設数と一致しない", file=sys.stderr)
        return 1
    (args.out / "index.html").write_text(list_html, encoding="utf-8")
    sitemap = render_sitemap(facilities)
    # self-check 6: sitemap の URL 数 = active 施設数 + トップ + 一覧
    if sitemap.count("<loc>") != active_count + 2:
        print("ERROR: sitemap の URL 数が想定と一致しない", file=sys.stderr)
        return 1
    args.sitemap.write_text(sitemap, encoding="utf-8")

    print(f"OK: {written} ページ生成(公園{parks}/無料{free}/プール{pools}、inactive 含む)"
          f" + 施設一覧 {active_count} 件 + sitemap {active_count + 2} URL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
