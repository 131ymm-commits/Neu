use core::ptr;

const MD5_BLOCK_SIZE: usize = 64;
const MD5_DIGEST_SIZE: usize = 16;
const MD5_BLOCK_WORDS: usize = 16;
const MD5_HASH_WORDS: usize = 4;

const MD5_H0: u32 = 0x67452301;
const MD5_H1: u32 = 0xefcdab89;
const MD5_H2: u32 = 0x98badcfe;
const MD5_H3: u32 = 0x10325476;

const HMAC_IPAD_VALUE: u8 = 0x36;
const HMAC_OPAD_VALUE: u8 = 0x5c;

#[repr(C)]
#[derive(Clone, Copy)]
pub struct md5_block_state {
    pub h: [u32; MD5_HASH_WORDS],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct md5_ctx {
    pub state: md5_block_state,
    pub bytecount: u64,
    pub buf: [u8; MD5_BLOCK_SIZE],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct hmac_md5_key {
    pub istate: md5_block_state,
    pub ostate: md5_block_state,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct hmac_md5_ctx {
    pub hash_ctx: md5_ctx,
    pub ostate: md5_block_state,
}

// Layout checks (build-time).
const _: () = assert!(core::mem::size_of::<md5_ctx>() == 88);
const _: () = assert!(core::mem::align_of::<md5_ctx>() == 8);
const _: () = assert!(core::mem::size_of::<hmac_md5_ctx>() == 104);
const _: () = assert!(core::mem::size_of::<hmac_md5_key>() == 32);

static MD5_IV: md5_block_state = md5_block_state {
    h: [MD5_H0, MD5_H1, MD5_H2, MD5_H3],
};

#[inline(always)]
fn f1(x: u32, y: u32, z: u32) -> u32 {
    z ^ (x & (y ^ z))
}
#[inline(always)]
fn f2(x: u32, y: u32, z: u32) -> u32 {
    f1(z, x, y)
}
#[inline(always)]
fn f3(x: u32, y: u32, z: u32) -> u32 {
    x ^ y ^ z
}
#[inline(always)]
fn f4(x: u32, y: u32, z: u32) -> u32 {
    y ^ (x | !z)
}

macro_rules! md5step {
    ($f:ident, $w:ident, $x:ident, $y:ident, $z:ident, $in:ident, $i:expr, $k:expr, $s:expr) => {
        $w = $w
            .wrapping_add($f($x, $y, $z))
            .wrapping_add($in[$i].wrapping_add($k));
        $w = $w.rotate_left($s).wrapping_add($x);
    };
}

/// Zero `n` bytes at `p` in a way the compiler may not elide.
unsafe fn memzero_explicit(p: *mut u8, n: usize) {
    let mut i = 0;
    while i < n {
        ptr::write_volatile(p.add(i), 0);
        i += 1;
    }
    core::sync::atomic::compiler_fence(core::sync::atomic::Ordering::SeqCst);
}

unsafe fn md5_block(state: *mut md5_block_state, data: *const u8) {
    let mut inp = [0u32; MD5_BLOCK_WORDS];
    ptr::copy_nonoverlapping(data, inp.as_mut_ptr() as *mut u8, MD5_BLOCK_SIZE);
    // le32_to_cpu_array: no-op on little-endian.

    let mut a = (*state).h[0];
    let mut b = (*state).h[1];
    let mut c = (*state).h[2];
    let mut d = (*state).h[3];

    md5step!(f1, a, b, c, d, inp, 0, 0xd76aa478, 7);
    md5step!(f1, d, a, b, c, inp, 1, 0xe8c7b756, 12);
    md5step!(f1, c, d, a, b, inp, 2, 0x242070db, 17);
    md5step!(f1, b, c, d, a, inp, 3, 0xc1bdceee, 22);
    md5step!(f1, a, b, c, d, inp, 4, 0xf57c0faf, 7);
    md5step!(f1, d, a, b, c, inp, 5, 0x4787c62a, 12);
    md5step!(f1, c, d, a, b, inp, 6, 0xa8304613, 17);
    md5step!(f1, b, c, d, a, inp, 7, 0xfd469501, 22);
    md5step!(f1, a, b, c, d, inp, 8, 0x698098d8, 7);
    md5step!(f1, d, a, b, c, inp, 9, 0x8b44f7af, 12);
    md5step!(f1, c, d, a, b, inp, 10, 0xffff5bb1, 17);
    md5step!(f1, b, c, d, a, inp, 11, 0x895cd7be, 22);
    md5step!(f1, a, b, c, d, inp, 12, 0x6b901122, 7);
    md5step!(f1, d, a, b, c, inp, 13, 0xfd987193, 12);
    md5step!(f1, c, d, a, b, inp, 14, 0xa679438e, 17);
    md5step!(f1, b, c, d, a, inp, 15, 0x49b40821, 22);

    md5step!(f2, a, b, c, d, inp, 1, 0xf61e2562, 5);
    md5step!(f2, d, a, b, c, inp, 6, 0xc040b340, 9);
    md5step!(f2, c, d, a, b, inp, 11, 0x265e5a51, 14);
    md5step!(f2, b, c, d, a, inp, 0, 0xe9b6c7aa, 20);
    md5step!(f2, a, b, c, d, inp, 5, 0xd62f105d, 5);
    md5step!(f2, d, a, b, c, inp, 10, 0x02441453, 9);
    md5step!(f2, c, d, a, b, inp, 15, 0xd8a1e681, 14);
    md5step!(f2, b, c, d, a, inp, 4, 0xe7d3fbc8, 20);
    md5step!(f2, a, b, c, d, inp, 9, 0x21e1cde6, 5);
    md5step!(f2, d, a, b, c, inp, 14, 0xc33707d6, 9);
    md5step!(f2, c, d, a, b, inp, 3, 0xf4d50d87, 14);
    md5step!(f2, b, c, d, a, inp, 8, 0x455a14ed, 20);
    md5step!(f2, a, b, c, d, inp, 13, 0xa9e3e905, 5);
    md5step!(f2, d, a, b, c, inp, 2, 0xfcefa3f8, 9);
    md5step!(f2, c, d, a, b, inp, 7, 0x676f02d9, 14);
    md5step!(f2, b, c, d, a, inp, 12, 0x8d2a4c8a, 20);

    md5step!(f3, a, b, c, d, inp, 5, 0xfffa3942, 4);
    md5step!(f3, d, a, b, c, inp, 8, 0x8771f681, 11);
    md5step!(f3, c, d, a, b, inp, 11, 0x6d9d6122, 16);
    md5step!(f3, b, c, d, a, inp, 14, 0xfde5380c, 23);
    md5step!(f3, a, b, c, d, inp, 1, 0xa4beea44, 4);
    md5step!(f3, d, a, b, c, inp, 4, 0x4bdecfa9, 11);
    md5step!(f3, c, d, a, b, inp, 7, 0xf6bb4b60, 16);
    md5step!(f3, b, c, d, a, inp, 10, 0xbebfbc70, 23);
    md5step!(f3, a, b, c, d, inp, 13, 0x289b7ec6, 4);
    md5step!(f3, d, a, b, c, inp, 0, 0xeaa127fa, 11);
    md5step!(f3, c, d, a, b, inp, 3, 0xd4ef3085, 16);
    md5step!(f3, b, c, d, a, inp, 6, 0x04881d05, 23);
    md5step!(f3, a, b, c, d, inp, 9, 0xd9d4d039, 4);
    md5step!(f3, d, a, b, c, inp, 12, 0xe6db99e5, 11);
    md5step!(f3, c, d, a, b, inp, 15, 0x1fa27cf8, 16);
    md5step!(f3, b, c, d, a, inp, 2, 0xc4ac5665, 23);

    md5step!(f4, a, b, c, d, inp, 0, 0xf4292244, 6);
    md5step!(f4, d, a, b, c, inp, 7, 0x432aff97, 10);
    md5step!(f4, c, d, a, b, inp, 14, 0xab9423a7, 15);
    md5step!(f4, b, c, d, a, inp, 5, 0xfc93a039, 21);
    md5step!(f4, a, b, c, d, inp, 12, 0x655b59c3, 6);
    md5step!(f4, d, a, b, c, inp, 3, 0x8f0ccc92, 10);
    md5step!(f4, c, d, a, b, inp, 10, 0xffeff47d, 15);
    md5step!(f4, b, c, d, a, inp, 1, 0x85845dd1, 21);
    md5step!(f4, a, b, c, d, inp, 8, 0x6fa87e4f, 6);
    md5step!(f4, d, a, b, c, inp, 15, 0xfe2ce6e0, 10);
    md5step!(f4, c, d, a, b, inp, 6, 0xa3014314, 15);
    md5step!(f4, b, c, d, a, inp, 13, 0x4e0811a1, 21);
    md5step!(f4, a, b, c, d, inp, 4, 0xf7537e82, 6);
    md5step!(f4, d, a, b, c, inp, 11, 0xbd3af235, 10);
    md5step!(f4, c, d, a, b, inp, 2, 0x2ad7d2bb, 15);
    md5step!(f4, b, c, d, a, inp, 9, 0xeb86d391, 21);

    (*state).h[0] = (*state).h[0].wrapping_add(a);
    (*state).h[1] = (*state).h[1].wrapping_add(b);
    (*state).h[2] = (*state).h[2].wrapping_add(c);
    (*state).h[3] = (*state).h[3].wrapping_add(d);
}

unsafe fn md5_blocks(state: *mut md5_block_state, data: *const u8, nblocks: usize) {
    let mut data = data;
    let mut n = nblocks;
    loop {
        md5_block(state, data);
        data = data.add(MD5_BLOCK_SIZE);
        n = n.wrapping_sub(1);
        if n == 0 {
            break;
        }
    }
}

#[inline(always)]
unsafe fn ctx_buf(ctx: *mut md5_ctx) -> *mut u8 {
    ptr::addr_of_mut!((*ctx).buf) as *mut u8
}

#[no_mangle]
pub extern "C" fn md5_init(ctx: *mut md5_ctx) {
    unsafe {
        (*ctx).state = MD5_IV;
        (*ctx).bytecount = 0;
    }
}

#[no_mangle]
pub extern "C" fn md5_update(ctx: *mut md5_ctx, data: *const u8, len: usize) {
    unsafe {
        let mut data = data;
        let mut len = len;
        let mut partial = ((*ctx).bytecount % MD5_BLOCK_SIZE as u64) as usize;
        let buf = ctx_buf(ctx);

        (*ctx).bytecount = (*ctx).bytecount.wrapping_add(len as u64);

        if partial.wrapping_add(len) >= MD5_BLOCK_SIZE {
            if partial != 0 {
                let l = MD5_BLOCK_SIZE - partial;
                ptr::copy_nonoverlapping(data, buf.add(partial), l);
                data = data.add(l);
                len = len.wrapping_sub(l);
                md5_blocks(ptr::addr_of_mut!((*ctx).state), buf, 1);
            }

            let nblocks = len / MD5_BLOCK_SIZE;
            len %= MD5_BLOCK_SIZE;

            if nblocks != 0 {
                md5_blocks(ptr::addr_of_mut!((*ctx).state), data, nblocks);
                data = data.add(nblocks * MD5_BLOCK_SIZE);
            }
            partial = 0;
        }
        if len != 0 {
            ptr::copy_nonoverlapping(data, buf.add(partial), len);
        }
    }
}

unsafe fn md5_final_inner(ctx: *mut md5_ctx, out: *mut u8) {
    let bitcount: u64 = (*ctx).bytecount << 3;
    let mut partial = ((*ctx).bytecount % MD5_BLOCK_SIZE as u64) as usize;
    let buf = ctx_buf(ctx);
    let state = ptr::addr_of_mut!((*ctx).state);

    *buf.add(partial) = 0x80;
    partial += 1;
    if partial > MD5_BLOCK_SIZE - 8 {
        ptr::write_bytes(buf.add(partial), 0, MD5_BLOCK_SIZE - partial);
        md5_blocks(state, buf, 1);
        partial = 0;
    }
    ptr::write_bytes(buf.add(partial), 0, MD5_BLOCK_SIZE - 8 - partial);
    ptr::write_unaligned(buf.add(MD5_BLOCK_SIZE - 8) as *mut u64, bitcount.to_le());
    md5_blocks(state, buf, 1);

    // cpu_to_le32_array: no-op on little-endian.
    ptr::copy_nonoverlapping(state as *const u8, out, MD5_DIGEST_SIZE);
}

#[no_mangle]
pub extern "C" fn md5_final(ctx: *mut md5_ctx, out: *mut u8) {
    unsafe {
        md5_final_inner(ctx, out);
        memzero_explicit(ctx as *mut u8, core::mem::size_of::<md5_ctx>());
    }
}

#[no_mangle]
pub extern "C" fn md5(data: *const u8, len: usize, out: *mut u8) {
    let mut ctx = md5_ctx {
        state: MD5_IV,
        bytecount: 0,
        buf: [0u8; MD5_BLOCK_SIZE],
    };
    md5_init(&mut ctx);
    md5_update(&mut ctx, data, len);
    md5_final(&mut ctx, out);
}

unsafe fn hmac_md5_preparekey_inner(
    istate: *mut md5_block_state,
    ostate: *mut md5_block_state,
    raw_key: *const u8,
    raw_key_len: usize,
) {
    let mut derived_key = [0u64; MD5_BLOCK_SIZE / 8];
    let b = derived_key.as_mut_ptr() as *mut u8;

    if raw_key_len > MD5_BLOCK_SIZE {
        md5(raw_key, raw_key_len, b);
    } else {
        ptr::copy_nonoverlapping(raw_key, b, raw_key_len);
    }

    let ipad = (u64::MAX / 255).wrapping_mul(HMAC_IPAD_VALUE as u64);
    for w in derived_key.iter_mut() {
        *w ^= ipad;
    }
    *istate = MD5_IV;
    md5_blocks(istate, b, 1);

    let opad = (u64::MAX / 255).wrapping_mul((HMAC_OPAD_VALUE ^ HMAC_IPAD_VALUE) as u64);
    for w in derived_key.iter_mut() {
        *w ^= opad;
    }
    *ostate = MD5_IV;
    md5_blocks(ostate, b, 1);

    memzero_explicit(b, MD5_BLOCK_SIZE);
}

#[no_mangle]
pub extern "C" fn hmac_md5_preparekey(key: *mut hmac_md5_key, raw_key: *const u8, raw_key_len: usize) {
    unsafe {
        hmac_md5_preparekey_inner(
            ptr::addr_of_mut!((*key).istate),
            ptr::addr_of_mut!((*key).ostate),
            raw_key,
            raw_key_len,
        );
    }
}

#[no_mangle]
pub extern "C" fn hmac_md5_init(ctx: *mut hmac_md5_ctx, key: *const hmac_md5_key) {
    unsafe {
        (*ctx).hash_ctx.state = (*key).istate;
        (*ctx).hash_ctx.bytecount = MD5_BLOCK_SIZE as u64;
        (*ctx).ostate = (*key).ostate;
    }
}

#[no_mangle]
pub extern "C" fn hmac_md5_init_usingrawkey(ctx: *mut hmac_md5_ctx, raw_key: *const u8, raw_key_len: usize) {
    unsafe {
        hmac_md5_preparekey_inner(
            ptr::addr_of_mut!((*ctx).hash_ctx.state),
            ptr::addr_of_mut!((*ctx).ostate),
            raw_key,
            raw_key_len,
        );
        (*ctx).hash_ctx.bytecount = MD5_BLOCK_SIZE as u64;
    }
}

fn hmac_md5_update(ctx: *mut hmac_md5_ctx, data: *const u8, data_len: usize) {
    unsafe {
        md5_update(ptr::addr_of_mut!((*ctx).hash_ctx), data, data_len);
    }
}

#[no_mangle]
pub extern "C" fn hmac_md5_final(ctx: *mut hmac_md5_ctx, out: *mut u8) {
    unsafe {
        let hctx = ptr::addr_of_mut!((*ctx).hash_ctx);
        let buf = ctx_buf(hctx);

        // Padded input for the outer hash goes into hash_ctx.buf.
        md5_final_inner(hctx, buf);
        ptr::write_bytes(buf.add(MD5_DIGEST_SIZE), 0, MD5_BLOCK_SIZE - MD5_DIGEST_SIZE);
        *buf.add(MD5_DIGEST_SIZE) = 0x80;
        ptr::write_unaligned(
            buf.add(MD5_BLOCK_SIZE - 8) as *mut u64,
            ((8 * (MD5_BLOCK_SIZE + MD5_DIGEST_SIZE)) as u64).to_le(),
        );

        let ostate = ptr::addr_of_mut!((*ctx).ostate);
        md5_blocks(ostate, buf, 1);
        // cpu_to_le32_array: no-op on little-endian.
        ptr::copy_nonoverlapping(ostate as *const u8, out, MD5_DIGEST_SIZE);

        memzero_explicit(ctx as *mut u8, core::mem::size_of::<hmac_md5_ctx>());
    }
}

#[no_mangle]
pub extern "C" fn hmac_md5(key: *const hmac_md5_key, data: *const u8, data_len: usize, out: *mut u8) {
    let zero_state = md5_block_state { h: [0; MD5_HASH_WORDS] };
    let mut ctx = hmac_md5_ctx {
        hash_ctx: md5_ctx {
            state: zero_state,
            bytecount: 0,
            buf: [0u8; MD5_BLOCK_SIZE],
        },
        ostate: zero_state,
    };
    hmac_md5_init(&mut ctx, key);
    hmac_md5_update(&mut ctx, data, data_len);
    hmac_md5_final(&mut ctx, out);
}

#[no_mangle]
pub extern "C" fn hmac_md5_usingrawkey(
    raw_key: *const u8,
    raw_key_len: usize,
    data: *const u8,
    data_len: usize,
    out: *mut u8,
) {
    let zero_state = md5_block_state { h: [0; MD5_HASH_WORDS] };
    let mut ctx = hmac_md5_ctx {
        hash_ctx: md5_ctx {
            state: zero_state,
            bytecount: 0,
            buf: [0u8; MD5_BLOCK_SIZE],
        },
        ostate: zero_state,
    };
    hmac_md5_init_usingrawkey(&mut ctx, raw_key, raw_key_len);
    hmac_md5_update(&mut ctx, data, data_len);
    hmac_md5_final(&mut ctx, out);
}
