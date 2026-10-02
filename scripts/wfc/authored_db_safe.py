"""Crash-isolating driver for authored_db.py shards.

Runs each missing package's shard in its OWN child process, a few at a time, polling every
child's working set; a child above --max-gb or --timeout is killed and the package is recorded
in logs/authored_db_failures.json instead of taking the pool (or the machine) down.
Background: 2026-10-01 full-parallel runs hit two hard machine crashes and one abruptly killed
worker; packages that never finished are retried here one by one.

  python authored_db_safe.py [--jobs 2] [--max-gb 8] [--timeout 1800] [--only PKG ...] [--merge | --merge-only]
"""
import ctypes, json, os, subprocess, sys, time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract  # noqa: E402

SHARDS = os.path.join(extract.MANI, 'authored_shards')
FAIL = os.path.join(extract.TOOLS, 'logs', 'authored_db_failures.json')
PY = sys.executable

class PMC(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD), ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t)]

def mem_gb(pid):
    k = ctypes.windll.kernel32; h = k.OpenProcess(0x1000 | 0x0010, False, pid)   # QUERY_LIMITED | VM_READ
    if not h: return 0.0, 0.0
    c = PMC(); c.cb = ctypes.sizeof(PMC)
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb); k.CloseHandle(h)
    return (c.PagefileUsage / 2 ** 30, c.PeakPagefileUsage / 2 ** 30) if ok else (0.0, 0.0)

def child(pkg):
    import authored_db
    authored_db.init_owner(os.path.join(extract.MANI, '_owner.db'))
    name, n, e = authored_db.shard_pkg(pkg)
    print(json.dumps({'pkg': name, 'objects': n, 'unparsed': e}), flush=True)

def main():
    a = sys.argv
    if '--child' in a: return child(a[a.index('--child') + 1])
    jobs = int(a[a.index('--jobs') + 1]) if '--jobs' in a else 2
    max_gb = float(a[a.index('--max-gb') + 1]) if '--max-gb' in a else 8.0
    tmo = float(a[a.index('--timeout') + 1]) if '--timeout' in a else 1800
    done = {f[:-9] for f in os.listdir(SHARDS) if f.endswith('.jsonl.gz')}
    todo = sorted(os.path.splitext(n)[0] for n in os.listdir(extract.COOKED)
                  if n.endswith('.xxx') and os.path.splitext(n)[0] not in done)
    if '--merge-only' in a:
        import authored_db; authored_db.merge(); return
    if '--only' in a: todo = [x for x in a[a.index('--only') + 1:] if not x.startswith('--')]
    fails = json.load(open(FAIL)) if os.path.exists(FAIL) else {}
    print('%d to do, jobs %d, max %.1f GB, timeout %ds' % (len(todo), jobs, max_gb, tmo), flush=True)
    t0 = time.time(); run = {}; q = list(todo); ok = 0
    while q or run:
        while q and len(run) < jobs:
            pkg = q.pop(0)
            p = subprocess.Popen([PY, '-u', __file__, '--child', pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 creationflags=0x4000)    # BELOW_NORMAL_PRIORITY_CLASS
            run[pkg] = (p, time.time(), 0.0)
        time.sleep(0.5)
        for pkg, (p, st, peak) in list(run.items()):
            cur, pk = mem_gb(p.pid); peak = max(peak, cur, pk); run[pkg] = (p, st, peak)
            why = None
            if p.poll() is None:
                if cur > max_gb: why = 'memory %.1f GB > %.1f' % (cur, max_gb)
                elif time.time() - st > tmo: why = 'timeout %ds' % tmo
                if why: p.kill(); p.wait()
                else: continue
            out, err = p.communicate()
            dt = time.time() - st; del run[pkg]
            if p.returncode == 0 and not why:
                ok += 1; fails.pop(pkg, None)
                print('  ok   %-40s %6.1fs peak %.2f GB  %s' % (pkg, dt, peak, out.decode(errors='replace').strip()[-120:]), flush=True)
            else:
                rec = {'returncode': p.returncode, 'reason': why or 'child exited abnormally (rc %s)' % p.returncode,
                       'seconds': round(dt, 1), 'peak_gb': round(peak, 2), 'stderr_tail': err.decode(errors='replace')[-1500:]}
                fails[pkg] = rec
                json.dump(fails, open(FAIL, 'w'), indent=1)
                print('  FAIL %-40s %s' % (pkg, rec['reason']), flush=True)
        if q and not run: pass
    json.dump(fails, open(FAIL, 'w'), indent=1)      # also clears packages that succeeded on retry
    print('done %d ok, %d failed (%s), %.0fs' % (ok, len(fails), FAIL, time.time() - t0), flush=True)
    if '--merge' in a:
        import authored_db
        authored_db.merge()

if __name__ == '__main__':
    main()
