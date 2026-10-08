# -*- coding: utf-8 -*-
"""Them mot thu muc skill vao repo roi day len GitHub.

Dung:
    python add-skill.py "C:\\duong\\dan\\den\\skill"
    python add-skill.py "C:\\duong\\dan\\den\\skill" ten-muon-dat

Hoac keo tha thu muc skill vao file "Them skill.bat".

Script se:
  1. kiem tra thu muc co SKILL.md khong
  2. lay ten tu dong 'name:' trong SKILL.md, khong co thi lay ten thu muc
  3. chep vao skills/<ten-skill>/
  4. git add / commit / push

Khong co gi phai sua o trang web - no doc thang cau truc repo nay.
"""

import os
import re
import shutil
import subprocess
import sys

NL = chr(10)
HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(HERE, "skills")
REPO_URL = "https://github.com/brian261101/All-of-50-Claude-Skill"
WEB_URL = "https://brian261101.github.io/#claude-skills"


def die(msg):
    print()
    print("  LOI: " + msg)
    print()
    sys.exit(1)


def run(args, **kw):
    return subprocess.run(args, cwd=HERE, text=True, encoding="utf-8",
                          capture_output=True, **kw)


def read_name(skill_md):
    """Doc 'name:' trong frontmatter."""
    try:
        txt = open(skill_md, encoding="utf-8").read()
    except Exception:
        return None
    m = re.match(r"^---\s*\n(.*?)\n---", txt, re.S)
    if not m:
        return None
    m2 = re.search(r"^name:\s*(.+)$", m.group(1), re.M)
    return m2.group(1).strip() if m2 else None


def ensure_identity():
    """Git tren may nay co the chua khai bao ten/email. Tu dat o muc repo."""
    name = run(["git", "config", "user.name"]).stdout.strip()
    email = run(["git", "config", "user.email"]).stdout.strip()
    if name and email:
        return

    login = mail = ""
    gh = run(["gh", "api", "user", "--jq", ".login"])
    if gh.returncode == 0:
        login = gh.stdout.strip()
        m = run(["gh", "api", "user", "--jq", ".email"]).stdout.strip()
        mail = "" if m in ("", "null") else m
    if login and not mail:
        mail = "%s@users.noreply.github.com" % login

    if not login:
        die('Git chua biet ban la ai. Chay mot lan hai lenh sau roi thu lai:'
            + NL + '         git config --global user.name  "Ten cua ban"'
            + NL + '         git config --global user.email "email@cua.ban"')

    run(["git", "config", "user.name", login])
    run(["git", "config", "user.email", mail])
    print("  Da dat danh tinh git cho repo nay: %s <%s>" % (login, mail))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        die("Chua chi ra thu muc skill.")

    src = os.path.abspath(sys.argv[1].rstrip('"').rstrip(os.sep) or ".")
    if not os.path.isdir(src):
        die("Khong phai thu muc: " + src)

    skill_md = None
    for f in os.listdir(src):
        if f.lower() == "skill.md":
            skill_md = os.path.join(src, f)
            break
    if not skill_md:
        die("Thu muc nay khong co SKILL.md nen trang web se khong hien no.\n"
            "       Them SKILL.md co frontmatter name: va description: truoc da.")

    name = sys.argv[2] if len(sys.argv) > 2 else (read_name(skill_md)
                                                  or os.path.basename(src))
    name = re.sub(r'[\\/:*?"<>|]', "-", name).strip()
    if not name:
        die("Ten skill rong.")

    dest = os.path.join(SKILLS, name)
    if os.path.isdir(dest):
        print("  Thu muc '%s' da co san - se ghi de noi dung." % name)
        shutil.rmtree(dest)

    shutil.copytree(src, dest)
    # bo rac khong can day len
    for root, dirs, files in os.walk(dest):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".idea")]
        for f in list(files):
            if f in ("Thumbs.db", ".DS_Store"):
                os.remove(os.path.join(root, f))

    n = sum(len(f) for _, _, f in os.walk(dest))
    print("  Da chep %d file vao skills/%s" % (n, name))

    ensure_identity()

    r = run(["git", "add", "-A", "skills"])
    if r.returncode:
        die("git add that bai:\n" + r.stderr)

    r = run(["git", "status", "--porcelain"])
    if not r.stdout.strip():
        print()
        print("  Khong co gi thay doi - skill nay da giong het ban tren GitHub.")
        return

    msg = "Them skill: %s" % name
    r = run(["git", "commit", "-q", "-m", msg])
    if r.returncode:
        die("git commit that bai:\n" + r.stderr + r.stdout)

    # Ban local co the lac hau neu ban vua upload gi do qua giao dien web.
    # Dong bo truoc, neu khong push se bi tu choi.
    print("  Dang dong bo voi GitHub...")
    r = run(["git", "pull", "-q", "--rebase", "origin", "main"])
    if r.returncode:
        die("Khong dong bo duoc voi GitHub:" + NL + r.stderr + r.stdout +
            NL + "       Ban local va ban tren GitHub dang xung dot."
            + NL + "       Mo thu muc nay roi xu ly bang tay truoc.")

    print("  Dang day len GitHub...")
    r = run(["git", "push", "-q", "origin", "main"])
    if r.returncode:
        die("git push that bai:\n" + r.stderr +
            "\n       Neu chua dang nhap, chay:  gh auth login")

    print()
    print("  XONG.")
    print("  Repo : %s/tree/main/skills/%s" % (REPO_URL, name))
    print("  Web  : %s" % WEB_URL)
    print()
    print("  Trang web co the mat toi 15 phut moi doi, vi no nho dem danh sach.")
    print("  Muon thay ngay thi bam Ctrl+F5 hoac mo cua so an danh.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
