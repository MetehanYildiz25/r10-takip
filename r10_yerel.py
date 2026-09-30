"""Bilgisayardaki zamanlanmış görev için sarmalayıcı.

GitHub'daki seen.json ile senkron çalışır: önce son durumu çeker, taramayı
yapar, güncel seen.json'u geri gönderir. Böylece GitHub Actions da
çalışsa aynı ilan iki kez bildirilmez.
"""
import subprocess
import sys

import r10_takip

NO_WINDOW = 0x08000000  # pythonw altında git için konsol penceresi açılmasın


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=r10_takip.BASE, capture_output=True, text=True,
        creationflags=NO_WINDOW if sys.platform == "win32" else 0,
    )


def main():
    pull = git("pull", "--rebase", "--autostash", "-q")
    if pull.returncode != 0:
        r10_takip.log(f"git pull başarısız: {pull.stderr.strip()[:200]}")
    try:
        r10_takip.main()
    finally:
        git("add", "seen.json")
        if git("diff", "--cached", "--quiet").returncode != 0:
            git("commit", "-q", "-m", "seen.json güncellendi (yerel)")
            push = git("push", "-q")
            if push.returncode != 0:
                r10_takip.log(f"git push başarısız: {push.stderr.strip()[:200]}")


if __name__ == "__main__":
    main()
