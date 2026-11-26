import os, sqlite3, glob, shutil

base = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data")
profiles = ["Default", "Profile", "Profile 1", "Profile 2"]

for p in profiles:
    cdir = os.path.join(base, p, "Network")
    cfile = os.path.join(cdir, "Cookies")
    if not os.path.exists(cfile):
        print(f"{p:10s} -> no Cookies DB")
        continue
    tmp = os.path.join(base, "_tmp_cookies.db")
    try:
        shutil.copyfile(cfile, tmp)
        con = sqlite3.connect(tmp)
        rows = con.execute("""
            SELECT host_key, COUNT(*) c FROM cookies
            WHERE host_key LIKE '%youtube.com%' OR host_key LIKE '%google.com%'
               OR host_key LIKE '%tiktok.com%' OR host_key LIKE '%instagram.com%'
               OR host_key LIKE '%facebook.com%'
            GROUP BY host_key ORDER BY c DESC LIMIT 6
        """).fetchall()
        con.close()
        os.remove(tmp)
        total = sum(r[1] for r in rows)
        print(f"{p:10s} -> {total:4d} social cookies :: {rows}")
    except Exception as e:
        print(f"{p:10s} -> ERR {e}")
