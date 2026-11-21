use core::ffi::{c_char, c_void};
use core::sync::atomic::{AtomicBool, Ordering};

type SwapFn = extern "C" fn(*mut c_void, *mut c_void, *mut c_void);
type LessFn = extern "C" fn(*const c_void, *const c_void, *mut c_void) -> bool;

#[repr(C)]
pub struct min_heap_char {
    pub nr: usize,
    pub size: usize,
    pub data: *mut c_char,
    pub preallocated: [c_char; 0],
}

#[repr(C)]
pub struct min_heap_callbacks {
    pub less: Option<LessFn>,
    pub swp: Option<SwapFn>,
}

const SWAP_WORDS_64: usize = 0;
const SWAP_WORDS_32: usize = 1;
const SWAP_BYTES: usize = 2;

/// WARN_ONCE: the warning is printed once per call site; no output is available here.
#[inline(always)]
fn warn_once(cond: bool, flag: &AtomicBool) -> bool {
    if cond {
        let _ = flag.swap(true, Ordering::Relaxed);
    }
    cond
}

#[inline(always)]
fn is_aligned(_base: *const c_void, size: usize, align: u8) -> bool {
    let lsbits = size as u8;
    (lsbits & (align - 1)) == 0
}

#[inline(always)]
unsafe fn swap_words_32(a: *mut c_void, b: *mut c_void, mut n: usize) {
    let a = a as *mut u8;
    let b = b as *mut u8;
    loop {
        n = n.wrapping_sub(4);
        let pa = a.wrapping_add(n) as *mut u32;
        let pb = b.wrapping_add(n) as *mut u32;
        let t = pa.read_unaligned();
        pa.write_unaligned(pb.read_unaligned());
        pb.write_unaligned(t);
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
unsafe fn swap_words_64(a: *mut c_void, b: *mut c_void, mut n: usize) {
    let a = a as *mut u8;
    let b = b as *mut u8;
    loop {
        n = n.wrapping_sub(8);
        let pa = a.wrapping_add(n) as *mut u64;
        let pb = b.wrapping_add(n) as *mut u64;
        let t = pa.read_unaligned();
        pa.write_unaligned(pb.read_unaligned());
        pb.write_unaligned(t);
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
unsafe fn swap_bytes(a: *mut c_void, b: *mut c_void, mut n: usize) {
    let a = a as *mut u8;
    let b = b as *mut u8;
    loop {
        n = n.wrapping_sub(1);
        let pa = a.wrapping_add(n);
        let pb = b.wrapping_add(n);
        let t = pa.read();
        pa.write(pb.read());
        pb.write(t);
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
fn select_swap_func(base: *const c_void, size: usize) -> usize {
    if is_aligned(base, size, 8) {
        SWAP_WORDS_64
    } else if is_aligned(base, size, 4) {
        SWAP_WORDS_32
    } else {
        SWAP_BYTES
    }
}

#[inline(always)]
unsafe fn do_swap(a: *mut c_void, b: *mut c_void, size: usize, swap_func: usize, privp: *mut c_void) {
    if swap_func == SWAP_WORDS_64 {
        swap_words_64(a, b, size);
    } else if swap_func == SWAP_WORDS_32 {
        swap_words_32(a, b, size);
    } else if swap_func == SWAP_BYTES {
        swap_bytes(a, b, size);
    } else {
        let f: SwapFn = core::mem::transmute::<usize, SwapFn>(swap_func);
        f(a, b, privp);
    }
}

#[inline(always)]
fn parent(mut i: usize, lsbit: u32, size: usize) -> usize {
    i = i.wrapping_sub(size);
    let m = (i & (lsbit as usize)).wrapping_neg();
    i = i.wrapping_sub(size & m);
    i / 2
}

#[inline(always)]
unsafe fn call_less(func: *const min_heap_callbacks, a: *const c_void, b: *const c_void, args: *mut c_void) -> bool {
    match (*func).less {
        Some(f) => f(a, b, args),
        None => core::hint::unreachable_unchecked(),
    }
}

#[inline(always)]
unsafe fn raw_swp(func: *const min_heap_callbacks) -> usize {
    core::mem::transmute::<Option<SwapFn>, usize>((*func).swp)
}

#[inline(always)]
fn off(data: *mut c_void, o: usize) -> *mut c_void {
    (data as *mut u8).wrapping_add(o) as *mut c_void
}

#[inline(always)]
unsafe fn min_heap_init_inline(heap: *mut min_heap_char, data: *mut c_void, size: usize) {
    (*heap).nr = 0;
    (*heap).size = size;
    if !data.is_null() {
        (*heap).data = data as *mut c_char;
    } else {
        (*heap).data = core::ptr::addr_of_mut!((*heap).preallocated) as *mut c_char;
    }
}

#[inline(always)]
unsafe fn min_heap_peek_inline(heap: *mut min_heap_char) -> *mut c_void {
    if (*heap).nr != 0 {
        (*heap).data as *mut c_void
    } else {
        core::ptr::null_mut()
    }
}

#[inline(always)]
unsafe fn min_heap_full_inline(heap: *mut min_heap_char) -> bool {
    (*heap).nr == (*heap).size
}

#[inline(always)]
unsafe fn min_heap_sift_down_inline(
    heap: *mut min_heap_char,
    pos: usize,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let lsbit: usize = elem_size & elem_size.wrapping_neg();
    let lsbit32 = lsbit as u32;
    let data = (*heap).data as *mut c_void;
    let mut swp = raw_swp(func);
    let a = pos.wrapping_mul(elem_size);
    let mut b: usize;
    let mut c: usize;
    let mut d: usize;
    let n = (*heap).nr.wrapping_mul(elem_size);

    if swp == 0 {
        swp = select_swap_func(data, elem_size);
    }

    b = a;
    loop {
        c = b.wrapping_mul(2).wrapping_add(elem_size);
        d = c.wrapping_add(elem_size);
        if !(d < n) {
            break;
        }
        b = if call_less(func, off(data, c), off(data, d), args) { c } else { d };
    }

    if d == n {
        b = c;
    }

    while b != a && call_less(func, off(data, a), off(data, b), args) {
        b = parent(b, lsbit32, elem_size);
    }

    c = b;
    while b != a {
        b = parent(b, lsbit32, elem_size);
        do_swap(off(data, b), off(data, c), elem_size, swp, args);
    }
}

#[inline(always)]
unsafe fn min_heap_sift_up_inline(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let lsbit: usize = elem_size & elem_size.wrapping_neg();
    let lsbit32 = lsbit as u32;
    let data = (*heap).data as *mut c_void;
    let mut swp = raw_swp(func);
    let mut a = idx.wrapping_mul(elem_size);
    let mut b: usize;

    if swp == 0 {
        swp = select_swap_func(data, elem_size);
    }

    while a != 0 {
        b = parent(a, lsbit32, elem_size);
        if call_less(func, off(data, b), off(data, a), args) {
            break;
        }
        do_swap(off(data, a), off(data, b), elem_size, swp, args);
        a = b;
    }
}

#[inline(always)]
unsafe fn min_heapify_all_inline(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    let mut i: isize = ((*heap).nr / 2).wrapping_sub(1) as isize;
    while i >= 0 {
        min_heap_sift_down_inline(heap, i as usize, elem_size, func, args);
        i -= 1;
    }
}

static WARN_POP: AtomicBool = AtomicBool::new(false);
static WARN_PUSH: AtomicBool = AtomicBool::new(false);
static WARN_DEL: AtomicBool = AtomicBool::new(false);

#[inline(always)]
unsafe fn min_heap_pop_inline(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data = (*heap).data as *mut c_void;

    if warn_once((*heap).nr == 0, &WARN_POP) {
        return false;
    }

    (*heap).nr -= 1;
    core::ptr::copy(
        off(data, (*heap).nr.wrapping_mul(elem_size)) as *const u8,
        data as *mut u8,
        elem_size,
    );
    min_heap_sift_down_inline(heap, 0, elem_size, func, args);

    true
}

#[inline(always)]
unsafe fn min_heap_pop_push_inline(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    core::ptr::copy((element as *const u8), (*heap).data as *mut u8, elem_size);
    min_heap_sift_down_inline(heap, 0, elem_size, func, args);
}

#[inline(always)]
unsafe fn min_heap_push_inline(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data = (*heap).data as *mut c_void;

    if warn_once((*heap).nr >= (*heap).size, &WARN_PUSH) {
        return false;
    }

    let pos = (*heap).nr;
    core::ptr::copy(
        element as *const u8,
        off(data, pos.wrapping_mul(elem_size)) as *mut u8,
        elem_size,
    );
    (*heap).nr += 1;

    min_heap_sift_up_inline(heap, elem_size, pos, func, args);

    true
}

#[inline(always)]
unsafe fn min_heap_del_inline(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    let data = (*heap).data as *mut c_void;
    let mut swp = raw_swp(func);

    if warn_once((*heap).nr == 0, &WARN_DEL) {
        return false;
    }

    if swp == 0 {
        swp = select_swap_func(data, elem_size);
    }

    (*heap).nr -= 1;
    if idx == (*heap).nr {
        return true;
    }
    do_swap(
        off(data, idx.wrapping_mul(elem_size)),
        off(data, (*heap).nr.wrapping_mul(elem_size)),
        elem_size,
        swp,
        args,
    );
    min_heap_sift_up_inline(heap, elem_size, idx, func, args);
    min_heap_sift_down_inline(heap, idx, elem_size, func, args);

    true
}

#[no_mangle]
pub extern "C" fn __min_heap_init(heap: *mut min_heap_char, data: *mut c_void, size: usize) {
    unsafe { min_heap_init_inline(heap, data, size) }
}

#[no_mangle]
pub extern "C" fn __min_heap_peek(heap: *mut min_heap_char) -> *mut c_void {
    unsafe { min_heap_peek_inline(heap) }
}

#[no_mangle]
pub extern "C" fn __min_heap_full(heap: *mut min_heap_char) -> bool {
    unsafe { min_heap_full_inline(heap) }
}

#[no_mangle]
pub extern "C" fn __min_heap_sift_down(
    heap: *mut min_heap_char,
    pos: usize,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    unsafe { min_heap_sift_down_inline(heap, pos, elem_size, func, args) }
}

#[no_mangle]
pub extern "C" fn __min_heap_sift_up(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    unsafe { min_heap_sift_up_inline(heap, elem_size, idx, func, args) }
}

#[no_mangle]
pub extern "C" fn __min_heapify_all(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    unsafe { min_heapify_all_inline(heap, elem_size, func, args) }
}

#[no_mangle]
pub extern "C" fn __min_heap_pop(
    heap: *mut min_heap_char,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    unsafe { min_heap_pop_inline(heap, elem_size, func, args) }
}

#[no_mangle]
pub extern "C" fn __min_heap_pop_push(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) {
    unsafe { min_heap_pop_push_inline(heap, element, elem_size, func, args) }
}

#[no_mangle]
pub extern "C" fn __min_heap_push(
    heap: *mut min_heap_char,
    element: *const c_void,
    elem_size: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    unsafe { min_heap_push_inline(heap, element, elem_size, func, args) }
}

#[no_mangle]
pub extern "C" fn __min_heap_del(
    heap: *mut min_heap_char,
    elem_size: usize,
    idx: usize,
    func: *const min_heap_callbacks,
    args: *mut c_void,
) -> bool {
    unsafe { min_heap_del_inline(heap, elem_size, idx, func, args) }
}
