#!/usr/bin/env python3
"""Self-test offline — chay TOAN BO luong agent bang provider 'mock' (khong can API key).

    python selftest.py

Kiem tra: nap skill builtin, phan loai chat/task, lap ke hoach, tu sinh + chay skill,
tai su dung skill da sinh, bo nho (memory), va tool schema kieu Hermes.
"""
import os
import sys
import shutil
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import PLANS_DIR, SKILLS_DIR          # noqa: E402
from core.config import Config                  # noqa: E402
from core.memory import Memory                  # noqa: E402
from core.orchestrator import SkillAgent        # noqa: E402
from core.tools import parse_tool_calls, to_openai_schema  # noqa: E402
from core.generator import validate                        # noqa: E402
from core.runner import run_skill                          # noqa: E402

MOCK = Config({"provider": "mock",
               "roles": {"chat": {"provider": "mock"}, "work": {"provider": "mock"}}})

NEEDVIDEO_SRC = """SKILL_META = {
    "name": "needvideo",
    "description": "tao bien ban cuoc hop tu video",
    "tags": ["video", "bien", "ban", "cuoc", "hop", "meeting"],
    "params": {
        "video_path": {"type": "str", "description": "duong dan video", "required": True},
        "output_path": {"type": "str", "description": "noi luu", "required": False},
    },
}


def run(**k):
    if not k.get("video_path"):
        return {"success": False, "error": "Video path not provided."}
    return {"success": True, "result": "ok " + k["video_path"]}
"""


NEEDLIB_SRC = """SKILL_META = {
    "name": "needlib",
    "description": "can thu vien ngoai depstest xulyabc",
    "tags": ["needlib", "depstest", "xulyabc", "thuvien"],
    "params": {},
}
import os
def run(**k):
    if not os.path.exists("_dep_ok.flag"):
        return {"success": False, "error": "pip install fakepkg123"}
    return {"success": True, "result": "da xu ly sau khi cai lib"}
"""


ECHO_SRC = """SKILL_META = {
    "name": "echoskill",
    "description": "buoc echo abc don gian",
    "tags": ["buoc", "echo", "abc"],
    "params": {},
}
def run(**k):
    return {"success": True, "result": "done"}
"""

NEEDFF_SRC = """SKILL_META = {
    "name": "needff",
    "description": "can ffmpeg de xu ly video xyz",
    "tags": ["needff", "ffmpegtest", "xyzvideo"],
    "params": {},
}
import os
def run(**k):
    if not os.path.exists("_ff_ok.flag"):
        return {"success": False, "error": "[WinError 2] cannot find 'ffmpeg'"}
    return {"success": True, "result": "da xu ly bang ffmpeg"}
"""

_passed = _failed = 0


def check(name, cond, extra=""):
    global _passed, _failed
    ok = bool(cond)
    print(f"  {'v' if ok else 'x'} {name}" + (f"  {extra}" if extra else ""))
    if ok:
        _passed += 1
    else:
        _failed += 1
    return ok


def main():
    before = {p.name for p in SKILLS_DIR.glob("*.py")}
    plans_before = {p.name for p in PLANS_DIR.glob("*.html")}
    mem_dir = tempfile.mkdtemp(prefix="javis_mem_")
    agent = SkillAgent(MOCK, memory=Memory(root=mem_dir, session="selftest"))

    print("\n[1] Registry nap skill builtin")
    names = agent.registry.names()
    check("get_video_info co mat", "get_video_info" in names)
    check("detect_scenes co mat", "detect_scenes" in names, f"(tong {len(names)} skill)")

    print("\n[2] Model chat - tro chuyen")
    r = agent.handle_message("xin chao Javis, ban khoe khong?")
    check("phan loai = chat", r.get("mode") == "chat")
    check("co cau tra loi", bool(r.get("reply")), f"-> {str(r.get('reply'))[:50]}")

    print("\n[3] Model chat - nhan dien tac vu + lap ke hoach")
    r = agent.handle_message("resize anh photo.jpg ve 800x600")
    check("phan loai = plan", r.get("mode") == "plan")
    check("co cac buoc", len(r.get("steps", [])) >= 2, f"({len(r.get('steps', []))} buoc)")
    plan_ok = r.get("plan_file") and (PLANS_DIR / r["plan_file"]).exists()
    check("file ke hoach HTML duoc tao", plan_ok, r.get("plan_file", ""))

    print("\n[4] Model work - tu sinh skill moi roi chay")
    ex = agent.execute_task("resize anh photo.jpg ve 800x600")
    check("thuc thi thanh cong", ex.get("success"))
    check("da SINH skill moi", ex.get("generated") is True, f"-> {ex.get('skill')}")
    check("params rut dung WxH", ex.get("params", {}).get("width") == 800
          and ex.get("params", {}).get("height") == 600, str(ex.get("params")))
    skill_file = SKILLS_DIR / f"{ex.get('skill')}.py"
    check("file skill duoc luu", skill_file.exists(), skill_file.name)

    print("\n[5] Model work - TAI SU DUNG skill da sinh (match)")
    ex2 = agent.execute_task("resize anh banner.png ve 1920x1080")
    check("thuc thi thanh cong", ex2.get("success"))
    check("KHONG sinh moi (match lai)", ex2.get("generated") is False, f"-> {ex2.get('skill')}")
    check("cung skill voi lan truoc", ex2.get("skill") == ex.get("skill"))

    print("\n[6] Bo nho - hoi thoai ngan han + facts dai han")
    hist = agent.memory.history()
    check("co luu lich su hoi thoai", len(hist) >= 2, f"({len(hist)} luot)")
    facts = agent.memory.all_facts()
    check("task da sinh fact dai han", len(facts) >= 1, f"({len(facts)} fact)")
    agent.memory.remember("Nguoi dung thich xuat anh o 800x600", kind="preference", tags=["resize", "anh"])
    rec = agent.memory.recall("resize anh", k=3)
    check("recall tra fact lien quan", any("800x600" in f["text"] for f in rec), f"({len(rec)} fact)")
    ctx = agent.memory.context_block("resize anh")
    check("context_block dung duoc ngu canh", bool(ctx))
    mem2 = Memory(root=mem_dir, session="selftest").load()
    check("facts con sau khi nap lai", len(mem2.all_facts()) >= 2, f"({len(mem2.all_facts())} fact)")

    print("\n[7] Tool schema kieu Hermes")
    schemas = agent.tool_schemas()
    check("moi skill export ra schema", len(schemas) == agent.registry.count(), f"({len(schemas)} tool)")
    one = to_openai_schema({"name": "resize_image", "description": "resize",
                            "params": {"input_path": {"type": "str", "required": True},
                                       "width": {"type": "int"}}})
    fn = one.get("function", {})
    check("schema dung dang function", one.get("type") == "function" and fn.get("name") == "resize_image")
    check("param map sang JSON Schema", fn["parameters"]["properties"]["width"]["type"] == "integer")
    check("required nhan dien dung", fn["parameters"]["required"] == ["input_path"])
    calls = parse_tool_calls('x <tool_call>{"name":"resize_image","arguments":{"width":800}}</tool_call>')
    check("parse tool_call tu output", len(calls) == 1 and calls[0]["arguments"]["width"] == 800)
    calls2 = parse_tool_calls('{"name":"get_video_info","arguments":{"input_path":"a.mp4"}}')
    check("parse JSON tran (khong the)", len(calls2) == 1 and calls2[0]["name"] == "get_video_info")

    print("\n[8] Kiem thu skill moi + memory tham gia chon skill")
    skfacts = [f for f in agent.memory.all_facts() if f.get("kind") == "skill"]
    check("da luu mo ta skill vao memory", len(skfacts) >= 1, f"({len(skfacts)} skill-fact)")
    ok_v, _ = validate(SKILLS_DIR / f"{ex.get('skill')}.py")
    check("validate skill hop le -> True", ok_v is True)
    bad_path = os.path.join(mem_dir, "bad_skill.py")
    with open(bad_path, "w", encoding="utf-8") as _f:
        _f.write("X = 1\n")   # thieu SKILL_META + run
    bad_ok, bad_msg = validate(bad_path)
    check("validate skill loi -> False", bad_ok is False, bad_msg)
    crashed = run_skill({"run": (lambda **k: 1 // 0)}, {})
    check("loi code -> _crashed=True", crashed.get("_crashed") is True)
    graceful = run_skill({"run": (lambda **k: {"success": False, "error": "thieu file"})}, {})
    check("loi du lieu -> khong _crashed", not graceful.get("_crashed"))
    recalled = agent._recall_skill("resize anh khac.png ve kich thuoc moi")
    check("memory goi y lai skill da dung", recalled == ex.get("skill"), f"-> {recalled}")

    print("\n[9] Tu doc lai skill + tu dien tham so + hoi lai")
    vm = agent.registry.get("video_meeting_summary")
    sch = agent._param_schema(vm) if vm else {}
    check("chuan hoa meta cu ('parameters'->params)",
          bool(sch) and sch.get("video_path", {}).get("required") is True, str(list(sch)))
    nv = SKILLS_DIR / "needvideo.py"
    nv.write_text(NEEDVIDEO_SRC, encoding="utf-8")
    agent.registry.load()
    r_ask = agent.execute_task("tao bien ban cuoc hop tu video")
    check("thieu param bat buoc -> hoi lai", r_ask.get("needs_input") == ["video_path"],
          str(r_ask.get("needs_input")))
    check("co cau hoi lai (ask)", bool(r_ask.get("ask")))
    vidf = "hop_selftest_xyz.mp4"
    with open(vidf, "w") as _vf:
        _vf.write("x")
    r_fill = agent.execute_task("tao bien ban cuoc hop tu video")
    check("tu dien video_path tu file trong thu muc",
          bool(r_fill.get("success")) and r_fill.get("params", {}).get("video_path") == vidf,
          str(r_fill.get("params")))
    check("tu dat ten output mac dinh", bool(r_fill.get("params", {}).get("output_path")))
    try:
        os.remove(vidf)
    except OSError:
        pass
    try:
        nv.unlink()
    except OSError:
        pass

    print("\n[10] Tu cai thu vien thieu roi chay lai")
    from core.orchestrator import _missing_package as _mp
    check("nhan dien 'pip install X'", _mp("pip install SpeechRecognition") == "SpeechRecognition")
    check("nhan dien 'No module named'", _mp("No module named 'cv2'") == "cv2")
    nl = SKILLS_DIR / "needlib.py"
    nl.write_text(NEEDLIB_SRC, encoding="utf-8")
    agent.registry.load()
    _flag = "_dep_ok.flag"
    if os.path.exists(_flag):
        os.remove(_flag)
    agent._pip_install = lambda pkg, _log: (open(_flag, "w").close() or True)
    r_dep = agent.execute_task("needlib depstest xulyabc thuvien")
    check("tu cai lib roi chay lai -> success", bool(r_dep.get("success")), str(r_dep.get("error")))
    if os.path.exists(_flag):
        os.remove(_flag)
    try:
        nl.unlink()
    except OSError:
        pass

    print("\n[11] Pipeline da buoc + tu cai cong cu he thong")
    from core.orchestrator import _missing_tool as _mt
    check("nhan dien cong cu thieu (WinError)", _mt("[WinError 2] cannot find 'ffmpeg'") == "ffmpeg")
    check("nhan dien 'command not found'", _mt("ffmpeg: command not found") == "ffmpeg")
    es = SKILLS_DIR / "echoskill.py"
    es.write_text(ECHO_SRC, encoding="utf-8")
    agent.registry.load()
    _orig_dec = agent._decompose
    agent._decompose = lambda t, _log: ["buoc echo abc mot", "buoc echo abc hai"]
    rp = agent.execute_task("lam A va lam B")
    agent._decompose = _orig_dec
    check("pipeline chay 2 buoc thanh cong",
          bool(rp.get("success")) and rp.get("steps_total") == 2,
          str([d.get("skill") for d in rp.get("done", [])]))
    try:
        es.unlink()
    except OSError:
        pass
    nf = SKILLS_DIR / "needff.py"
    nf.write_text(NEEDFF_SRC, encoding="utf-8")
    agent.registry.load()
    _ff = "_ff_ok.flag"
    if os.path.exists(_ff):
        os.remove(_ff)
    agent._install_system_tool = lambda t, _log: (open(_ff, "w").close() or True)
    r_ff = agent.execute_task("needff ffmpegtest xyzvideo")
    check("tu cai cong cu roi chay lai", bool(r_ff.get("success")), str(r_ff.get("error")))
    if os.path.exists(_ff):
        os.remove(_ff)
    try:
        nf.unlink()
    except OSError:
        pass

    # ---- don dep ----
    shutil.rmtree(mem_dir, ignore_errors=True)
    for p in SKILLS_DIR.glob("*.py"):
        if p.name not in before:
            p.unlink()
    for p in PLANS_DIR.glob("*.html"):
        if p.name not in plans_before:
            p.unlink()

    print("\n" + "=" * 44)
    print(f"  KET QUA: {_passed} PASS / {_failed} FAIL")
    print("=" * 44)
    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
