// LINUX-02, заглушка для сухого прогона обвязки (написана Claude по коду lib/errseq.c, не головой): с намеренной ошибкой: сложение счётчика без заворачивания — паника при переполнении.
use core::ffi::c_int;
use core::sync::atomic::{AtomicU32, Ordering::SeqCst};
const MAX_ERRNO: u32 = 4095;
const ERRSEQ_SHIFT: u32 = 12; // ilog2(MAX_ERRNO) + 1
const ERRSEQ_SEEN: u32 = 1 << ERRSEQ_SHIFT;
const ERRNO_MASK: u32 = ERRSEQ_SEEN - 1;
const ERRSEQ_CTR_INC: u32 = 1 << (ERRSEQ_SHIFT + 1);
unsafe fn at<'a>(p: *mut u32) -> &'a AtomicU32 { AtomicU32::from_ptr(p) }
#[no_mangle]
pub unsafe extern "C" fn errseq_set(eseq: *mut u32, err: c_int) -> u32 {
    let a = at(eseq);
    let mut old = a.load(SeqCst);
    if err == 0 || (err.wrapping_neg() as u32) > MAX_ERRNO { return old; }
    loop {
        let mut new = (old & !(ERRNO_MASK | ERRSEQ_SEEN)) | (err.wrapping_neg() as u32);
        if old & ERRSEQ_SEEN != 0 { new += ERRSEQ_CTR_INC; }
        if new == old { return new; }
        let cur = match a.compare_exchange(old, new, SeqCst, SeqCst) { Ok(v) => v, Err(v) => v };
        if cur == old || cur == new { return cur; }
        old = cur;
    }
}
#[no_mangle]
pub unsafe extern "C" fn errseq_sample(eseq: *mut u32) -> u32 {
    let old = at(eseq).load(SeqCst);
    if old & ERRSEQ_SEEN == 0 { 0 } else { old }
}
#[no_mangle]
pub unsafe extern "C" fn errseq_check(eseq: *mut u32, since: u32) -> c_int {
    let cur = at(eseq).load(SeqCst);
    if cur == since { return 0; }
    ((cur & ERRNO_MASK) as c_int).wrapping_neg()
}
#[no_mangle]
pub unsafe extern "C" fn errseq_check_and_advance(eseq: *mut u32, since: *mut u32) -> c_int {
    let a = at(eseq);
    let mut old = a.load(SeqCst);
    while old != *since {
        let new = old | ERRSEQ_SEEN;
        if new != old {
            let cur = match a.compare_exchange(old, new, SeqCst, SeqCst) { Ok(v) => v, Err(v) => v };
            if cur != old { old = cur; continue; }
        }
        *since = new;
        return ((new & ERRNO_MASK) as c_int).wrapping_neg();
    }
    0
}
