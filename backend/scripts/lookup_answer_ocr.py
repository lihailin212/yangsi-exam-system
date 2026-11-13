# -*- coding: utf-8 -*-
"""把每道题在答案卷里的「答案 + 解析」找出来。

答案卷不重复题干，只有「8.答案：E。解析：……」，所以按题号对：
试卷 OCR 里拿到题号，到同一份卷子的答案卷里找同题号的那一段。
"""
import json
import pathlib
import re

BACKEND = pathlib.Path(__file__).resolve().parent.parent
OCR = BACKEND / ".cache" / "ocr"
OUT = BACKEND / ".cache" / "_qfix"


def num_of(text):
    m = re.match(r"^\s*(\d{1,3})\s*[.．、]", text or "")
    return int(m.group(1)) if m else None


def main():
    tasks = json.loads((OUT / "tasks.json").read_text(encoding="utf-8"))
    ok = [t for t in tasks if t["ok"]]

    # 答案卷：文件名 -> 排序后的框
    ans = {}
    for f in sorted(OCR.glob("*答案*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        boxes = sorted([b for b in d.get("boxes", []) if b.get("t")], key=lambda b: b.get("y", 0))
        ans.setdefault(f.name.split("__")[0], []).append((f, boxes))

    lines = []
    for t in ok:
        # 题号：从试卷页里找题干那一行的编号
        qnum = None
        cache = t.get("cache") or f"{t['pdf']}__p{t['page']:04d}.json"
        if cache and (OCR / cache).exists():
            d = json.loads((OCR / cache).read_text(encoding="utf-8"))
            stem_key = re.sub(r"[\s，,。．.、：:；;？?！!（）()「」“”\"'【】\[\]]+", "", t["stem"])[:8]
            for b in d.get("boxes", []):
                txt = re.sub(r"^\d{1,3}\s*[.．、]\s*", "", (b.get("t") or "").strip())
                if stem_key and stem_key in re.sub(r"[\s，,。．.、：:；;？?！!（）()「」“”\"'【】\[\]]+", "", txt):
                    qnum = num_of(b.get("t") or "")
                    break
        found = ""
        if qnum:
            pref = t["pdf"].replace("试卷", "答案")
            for f, boxes in ans.get(pref, []):
                for i, b in enumerate(boxes):
                    txt = (b.get("t") or "").strip()
                    if not re.match(r"^\s*%d\s*[.．、]" % qnum, txt):
                        continue
                    chunk = " ".join((bb.get("t") or "") for bb in boxes[i:i + 6])
                    if "答案" in chunk[:30]:
                        found = chunk
                        break
                if found:
                    break
        lines.append(f"### id={t['id']} qnum={qnum} answer={t['answer']}\n"
                     f"    题干: {t['stem']}\n"
                     f"    答案卷: {found[:260] if found else '（没找到）'}\n")
    (OUT / "answers.txt").write_text("\n".join(lines), encoding="utf-8")
    hit = sum(1 for x in lines if "（没找到）" not in x)
    print(f"{len(lines)} 题，找到答案卷解析 {hit} 题")


if __name__ == "__main__":
    main()
