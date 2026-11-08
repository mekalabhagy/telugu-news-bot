"""Telugu news channel bot.

  python main.py demo                 render 3 sample cards (no API keys needed)
  python main.py run [--dry-run]      fetch -> summarise -> render -> queue/publish
  python main.py approve [--all|ID]   publish cards waiting in queue/pending
  python main.py list                 show the pending queue
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import config
import db
import render
import sources


def source_line(names):
    names = [n for n in names if n]
    if not names:
        return ""
    shown = ", ".join(names[:2])
    return shown + (f" +{len(names) - 2}" if len(names) > 2 else "")


# --------------------------------------------------------------------------- demo
DEMO = [
    {"category": "local",
     "headline_te": "హైదరాబాద్‌లో భారీ వర్షం, పలు ప్రాంతాల్లో ట్రాఫిక్ జామ్",
     "summary_te": "నగరంలోని పలు ప్రాంతాల్లో కురిసిన భారీ వర్షానికి రోడ్లపై నీరు నిలిచింది. వాహనదారులు ట్రాఫిక్‌లో చిక్కుకున్నారు. అవసరమైతే తప్ప బయటకు రావద్దని అధికారులు సూచించారు."},
    {"category": "business",
     "headline_te": "స్టాక్ మార్కెట్లు లాభాల్లో ముగిశాయి, ఐటీ షేర్లకు డిమాండ్",
     "summary_te": "ఈ రోజు ట్రేడింగ్‌లో సూచీలు పెరిగాయి. ముఖ్యంగా ఐటీ, బ్యాంకింగ్ షేర్లలో కొనుగోళ్లు కనిపించాయి. మదుపరులు జాగ్రత్తగా వ్యవహరించాలని నిపుణులు సూచిస్తున్నారు."},
    {"category": "sports",
     "headline_te": "భారత్ ఘన విజయం, సిరీస్‌లో ఆధిక్యం",
     "summary_te": "చివరి ఓవర్ వరకు ఉత్కంఠగా సాగిన మ్యాచ్‌లో భారత జట్టు గెలిచింది. దీంతో సిరీస్‌లో ఆధిక్యం సాధించింది."},
]


def cmd_demo(_):
    for i, card in enumerate(DEMO, 1):
        p = render.render_card(card, config.OUT_DIR / f"demo_{i}.jpg",
                               source_line="Sample Source, Sample News +2", demo=True)
        print("wrote", p)


# ---------------------------------------------------------------------------- run
def _publish(card, img_path, fp, stems):
    import publish

    url = publish.host_image(Path(img_path))
    caption = publish.build_caption(card, card["source_line"])
    media_id = publish.post_image(url, caption)
    db.update_status(fp, "published", ig_id=media_id)
    return media_id


def cmd_run(args):
    import summarize

    mode = "dry" if args.dry_run else config.POST_MODE
    clusters = sources.build_clusters()
    print(f"[run] {len(clusters)} story clusters, mode={mode}")
    made = 0
    for c in clusters:
        if made >= (args.count or config.POSTS_PER_RUN):
            break
        if c.n_sources < config.MIN_SOURCES:
            continue
        fp = c.fingerprint
        if db.seen(fp, c.stems):
            continue
        try:
            card = summarize.make_card(c)
        except Exception as e:
            print(f"[run] summarise failed ({e}); skipping {c.rep.title[:50]}")
            continue
        if card.get("skip"):
            db.record(fp, c.stems, c.rep.title, "", "skipped", note=card.get("skip_reason", ""))
            continue
        if config.SKIP_SENSITIVE and card.get("sensitive"):
            db.record(fp, c.stems, c.rep.title, "", "skipped_sensitive")
            print(f"[run] sensitive, skipped: {c.rep.title[:60]}")
            continue

        card["source_line"] = source_line(c.sources)
        stamp = time.strftime("%Y%m%d_%H%M%S") + f"_{fp[:6]}"
        img = render.render_card(card, config.OUT_DIR / f"{stamp}.jpg", card["source_line"])
        db.record(fp, c.stems, card["headline_te"], card["source_line"], "rendered")
        card["fp"], card["stems"] = fp, sorted(c.stems)

        if mode == "dry":
            print(f"[dry] {img}")
        elif mode == "review":
            shutil.copy(img, config.QUEUE_PENDING / f"{stamp}.jpg")
            (config.QUEUE_PENDING / f"{stamp}.json").write_text(
                json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
            db.update_status(fp, "pending_review")
            print(f"[queue] {stamp}  {card['headline_te']}")
        else:  # auto
            try:
                mid = _publish(card, img, fp, c.stems)
                print(f"[posted] {mid}  {card['headline_te']}")
            except Exception as e:
                db.update_status(fp, "publish_failed", note=str(e)[:300])
                print(f"[run] publish failed: {e}")
                continue
        made += 1


# ------------------------------------------------------------------------ approve
def _pending():
    return sorted(config.QUEUE_PENDING.glob("*.json"))


def cmd_list(_):
    for p in _pending():
        card = json.loads(p.read_text(encoding="utf-8"))
        print(p.stem, "|", card["headline_te"])
    if not _pending():
        print("queue is empty")


def cmd_approve(args):
    todo = [p for p in _pending() if args.all or p.stem == args.id]
    if not todo:
        print("nothing to approve (use --all or an ID from `list`)")
        return
    for p in todo:
        card = json.loads(p.read_text(encoding="utf-8"))
        img = p.with_suffix(".jpg")
        try:
            mid = _publish(card, img, card["fp"], set(card["stems"]))
        except Exception as e:
            db.update_status(card["fp"], "publish_failed", note=str(e)[:300])
            print(f"[approve] failed {p.stem}: {e}")
            continue
        shutil.move(str(img), config.QUEUE_PUBLISHED / img.name)
        shutil.move(str(p), config.QUEUE_PUBLISHED / p.name)
        print(f"[posted] {mid}  {card['headline_te']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo").set_defaults(fn=cmd_demo)
    r = sub.add_parser("run")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--count", type=int)
    r.set_defaults(fn=cmd_run)
    a = sub.add_parser("approve")
    a.add_argument("id", nargs="?")
    a.add_argument("--all", action="store_true")
    a.set_defaults(fn=cmd_approve)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
