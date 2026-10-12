/*
 * allow_ptrace.so — LD_PRELOAD helper (freestanding, no libc).
 *
 * Yama ptrace_scope=1 lets a process be traced only by its ancestors, which
 * blocks `gdb -p` on the Cxbx loader (reparented under init). Calling
 * prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY) from inside the target marks it
 * freely attachable, so we can sample its threads without root.
 *
 * The only compiler available is musl-targeting, whose libc.so is an ld script
 * that glibc's loader rejects. So we avoid libc entirely: invoke the prctl
 * syscall directly (#157 on x86_64) and link with -nostdlib.
 *
 * Build: gcc -shared -fPIC -nostdlib -O2 -o allow_ptrace.so allow_ptrace.c
 */

#define PR_SET_PTRACER 0x59616d61
#define PR_SET_PTRACER_ANY ((unsigned long)-1)
#define SYS_PRCTL 157

static long raw_prctl(unsigned long op, unsigned long a2, unsigned long a3,
                      unsigned long a4, unsigned long a5)
{
    long ret;
    register long rax __asm__("rax") = SYS_PRCTL;
    register long rdi __asm__("rdi") = (long)op;
    register long rsi __asm__("rsi") = (long)a2;
    register long rdx __asm__("rdx") = (long)a3;
    register long r10 __asm__("r10") = (long)a4;
    register long r8 __asm__("r8") = (long)a5;
    __asm__ volatile("syscall"
                     : "=a"(ret)
                     : "a"(rax), "D"(rdi), "S"(rsi), "d"(rdx), "r"(r10), "r"(r8)
                     : "rcx", "r11", "memory");
    return ret;
}

__attribute__((constructor)) static void allow_ptrace(void)
{
    raw_prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY, 0, 0, 0);
}
