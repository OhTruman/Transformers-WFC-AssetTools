r"""Run a pipeline step inside a Windows Job Object with a hard memory cap (deliberate memory guard).

The child (and anything it spawns) is assigned to a job with JOB_OBJECT_LIMIT_JOB_MEMORY: allocations beyond the cap fail
inside the child instead of exhausting system memory, and KILL_ON_JOB_CLOSE ends the job if this runner exits.
Reports exit code, wall time and the job's peak committed memory.

  python run_bounded.py --cap-gb 6 [--log logs/x.log] -- <python script> [args...]

Performance holds (Integration 2026-10-11): a lane's hold is F:\Transformers Rebuild\<lane>\work\PERF_HOLD (presence = hold active).
Waiting is done by scripts/wfc/hold_wait.cmd before python starts (lane watchdogs flag any foreign python.exe, so a waiting python
would itself contaminate a timed run); this runner only refuses to start (exit 75) when a hold exists. WFC_GATE_IGNORE_HOLD=1
skips only AssetTools' own hold.
"""
import argparse, ctypes, glob, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))   # F:\Transformers Rebuild

def active_holds():
    own = os.path.join(ROOT, 'AssetTools', 'work', 'PERF_HOLD')
    return [f for f in glob.glob(os.path.join(ROOT, '*', 'work', 'PERF_HOLD'))
            if not (os.environ.get('WFC_GATE_IGNORE_HOLD') == '1' and os.path.normcase(f) == os.path.normcase(own))]
from ctypes import wintypes as W

JobObjectExtendedLimitInformation = 9
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x200
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                                                  'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

class BASIC(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong), ('PerJobUserTimeLimit', ctypes.c_longlong),
                ('LimitFlags', W.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t), ('MaximumWorkingSetSize', ctypes.c_size_t),
                ('ActiveProcessLimit', W.DWORD), ('Affinity', ctypes.c_size_t), ('PriorityClass', W.DWORD),
                ('SchedulingClass', W.DWORD)]

class EXTENDED(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', BASIC), ('IoInfo', IO_COUNTERS), ('ProcessMemoryLimit', ctypes.c_size_t),
                ('JobMemoryLimit', ctypes.c_size_t), ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cap-gb', type=float, default=6.0)
    ap.add_argument('--log')
    ap.add_argument('cmd', nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == '--' else a.cmd
    on = active_holds()
    if on: print('run_bounded: refused, PERF_HOLD present (wait with hold_wait.cmd): %s' % ', '.join(on)); sys.exit(75)
    k = ctypes.windll.kernel32
    k.CreateJobObjectW.restype = W.HANDLE
    k.OpenProcess.restype = W.HANDLE
    job = k.CreateJobObjectW(None, None)
    info = EXTENDED()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_JOB_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    info.JobMemoryLimit = int(a.cap_gb * 2**30)
    if not k.SetInformationJobObject(W.HANDLE(job), JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)):
        sys.exit('SetInformationJobObject failed')
    out = open(a.log, 'w', encoding='utf-8') if a.log else None
    t0 = time.time()
    p = subprocess.Popen([sys.executable] + cmd, stdout=out or None, stderr=subprocess.STDOUT if out else None,
                         creationflags=0x00000004)   # CREATE_SUSPENDED: assign before it runs
    h = k.OpenProcess(0x1F0FFF, False, p.pid)
    if not k.AssignProcessToJobObject(W.HANDLE(job), W.HANDLE(h)):
        p.kill(); sys.exit('AssignProcessToJobObject failed')
    # resume the main thread (suspended at creation)
    ntdll = ctypes.windll.ntdll
    ntdll.NtResumeProcess(W.HANDLE(h))
    rc = p.wait()
    q = EXTENDED()
    k.QueryInformationJobObject(W.HANDLE(job), JobObjectExtendedLimitInformation, ctypes.byref(q), ctypes.sizeof(q), None)
    line = 'run_bounded: rc=%s  wall=%.1fs  peak_job_memory=%.2f GB  cap=%.1f GB  cmd=%s' % (
        rc, time.time() - t0, q.PeakJobMemoryUsed / 2**30, a.cap_gb, ' '.join(cmd))
    print(line)
    if out:
        out.close(); open(a.log, 'a', encoding='utf-8').write(os.linesep + line + os.linesep)
    k.CloseHandle(W.HANDLE(h)); k.CloseHandle(W.HANDLE(job))
    sys.exit(rc)

if __name__ == '__main__':
    main()
